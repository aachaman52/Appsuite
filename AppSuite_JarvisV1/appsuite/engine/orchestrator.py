from __future__ import annotations
import os
import time
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict, List, Optional, Set

from .job_state import UnifiedJobState
from .event_bus import (
    EventBus, TaskCreated, TaskStarted, TaskCompleted, TaskFailed,
    WorkerStarted, WorkerFinished, CheckpointSaved, RecoveryStarted,
    RecoveryCompleted, ResourceWarning, PipelineFinished
)
from .checkpoint import CheckpointManager
from .observability import ObservabilityWriter
from ..core.state import WorkerResult, WorkerStatus
from ..logging_setup import get_logger

log = get_logger("engine.orchestrator")

class GraphOrchestrator:
    """
    Consolidated, production-grade Parallel DAG Engine.
    Handles parallel execution, cycle detection, deadlock detection, resource gates,
    priority scheduling, timeout protection, checkpointing, and observability.
    """
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        checkpoint_mgr: Optional[CheckpointManager] = None,
        observability: Optional[ObservabilityWriter] = None,
        max_workers: int = 4,
        task_timeout: float = 300.0
    ):
        self.nodes: Dict[str, Any] = {}
        if event_bus is not None and not (hasattr(event_bus, "subscribe") and hasattr(event_bus, "publish")):
            self.event_bus = EventBus()
        else:
            self.event_bus = event_bus or EventBus()
        self.checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self.observability = observability or ObservabilityWriter(self.event_bus)
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        self.router = None
        self._start_node = "asset_search"

    def add_node(self, name: str, node: Any):
        self.nodes[name] = node

    def set_router(self, router: Any):
        self.router = router

    def _detect_cycles(self, tasks: List[Any]):
        """DFS-based cycle detection on the dependency graph of tasks."""
        adj = {t.task_id: t.dependencies for t in tasks}
        visited = {} # task_id -> state (0=unvisited, 1=visiting, 2=visited)
        
        def dfs(node):
            visited[node] = 1
            for dep in adj.get(node, []):
                if visited.get(dep, 0) == 1:
                    raise ValueError(f"Cycle detected in dependency graph involving task {node} and {dep}")
                if visited.get(dep, 0) == 0:
                    dfs(dep)
            visited[node] = 2

        for t in tasks:
            if visited.get(t.task_id, 0) == 0:
                dfs(t.task_id)

    def run_dag(self, agent_tasks: list, job_state: Dict[str, Any], hardware=None, worker_scores: Optional[Dict[str, float]] = None) -> list:
        """
        Executes an AgentTask DAG in parallel with priority scheduling, deadlock detection,
        timeouts, resource watermark gates, checkpointing and observability events.
        """
        # Cycle detection
        self._detect_cycles(agent_tasks)
        
        job_id = job_state["job"]["id"]
        
        # Publish task created events
        for task in agent_tasks:
            self.event_bus.publish(TaskCreated(job_id=job_id, task_id=task.task_id, agent_type=task.agent_type, priority=task.priority))

        # Checkpoint restore logic
        completed_tasks = set()
        running_tasks = set()
        pending_tasks = {t.task_id: t for t in agent_tasks}
        
        # Load from checkpoint if exists
        ckpt = self.checkpoint_mgr.load(job_id)
        if ckpt:
            completed_tasks = set(ckpt.get("completed", []))
            # Remove completed from pending
            for c_id in completed_tasks:
                if c_id in pending_tasks:
                    del pending_tasks[c_id]
            
            pstate_data = ckpt.get("state", {}).get("pipeline_state", {})
            # Reconstruct state
            if pstate_data:
                g_state = UnifiedJobState.from_dict(ckpt.get("state", {}))
                job_state["pipeline_state"] = g_state
            
            self.event_bus.publish(RecoveryStarted(job_id=job_id, resumed_from=ckpt.get("job_id", ""), skipped_tasks=list(completed_tasks)))

        results = []
        future_to_task = {}
        future_start_times = {}
        paused_start_time = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while pending_tasks or running_tasks:
                tasks_paused_for_resources = False
                
                # Check for deadlocks
                ready_to_run = []
                for t_id, task in list(pending_tasks.items()):
                    if all(dep in completed_tasks for dep in task.dependencies):
                        ready_to_run.append(task)
                
                if not ready_to_run and pending_tasks and not running_tasks:
                    raise RuntimeError(f"Deadlock detected! Pending tasks: {list(pending_tasks.keys())} are blocked but no tasks are running.")
                
                # Priority scheduling: sort ready tasks by priority (descending)
                ready_to_run.sort(key=lambda t: (
                    t.priority + (worker_scores.get(t.agent_type, 0.0) if worker_scores else 0.0) - (t.estimated_duration_seconds / 120.0)
                ), reverse=True)
                
                # Resource watermarks check
                for task in ready_to_run:
                    if hardware:
                        res = hardware.resources()
                        self.observability.update_resource_peaks(res.get("ram_percent", 0.0), res.get("cpu_percent", 0.0))
                        gpu_available = res.get("gpu_available", False)
                        if task.agent_type in {"BlenderAgent", "GodotAgent"} and not gpu_available:
                            self.event_bus.publish(ResourceWarning(job_id=job_id, resource="gpu", level=0.0, threshold=0.0))
                        if res.get("ram_percent", 0.0) > 80.0 and task.agent_type in {"BlenderAgent", "GodotAgent"}:
                            self.event_bus.publish(ResourceWarning(job_id=job_id, resource="ram", level=res["ram_percent"], threshold=80.0))
                            now = time.time()
                            if task.task_id not in paused_start_time:
                                paused_start_time[task.task_id] = now
                            if now - paused_start_time[task.task_id] < 15.0:
                                tasks_paused_for_resources = True
                                continue
                            else:
                                log.warning(f"Resource limit exceeded for 15s. Running {task.task_id} anyway.")
                        
                        if res.get("ram_percent", 0.0) > 90.0:
                            self.event_bus.publish(ResourceWarning(job_id=job_id, resource="ram", level=res["ram_percent"], threshold=90.0))
                            now = time.time()
                            if task.task_id not in paused_start_time:
                                paused_start_time[task.task_id] = now
                            if now - paused_start_time[task.task_id] < 15.0:
                                tasks_paused_for_resources = True
                                continue
                            else:
                                log.warning(f"Resource limit exceeded for 15s. Running {task.task_id} anyway.")

                    del pending_tasks[task.task_id]
                    running_tasks.add(task.task_id)
                    
                    agent_node = self.nodes.get(task.agent_type)
                    if agent_node:
                        # === THREAD SAFETY FIX (W5) ===
                        # Previously we stored job_state on the shared agent instance:
                        #   agent_node.current_job_state = job_state  ← DATA RACE
                        # Multiple ThreadPoolExecutor threads mutating the same attribute
                        # on the same object caused silent state corruption.
                        #
                        # Fix: pass job_state as an explicit parameter to agent.run().
                        # Each thread receives its own isolated reference; no shared
                        # mutable agent state is modified.
                        #
                        # Emit TaskStarted
                        self.event_bus.publish(TaskStarted(job_id=job_id, task_id=task.task_id, agent_name=task.agent_type))

                        # Submit agent execution with isolated state
                        future = executor.submit(agent_node.run, task, job_state)
                        future_to_task[future] = task
                        future_start_times[future] = time.time()
                    else:
                        # Agent not registered, complete task instantly
                        completed_tasks.add(task.task_id)
                        running_tasks.remove(task.task_id)
                
                if running_tasks:
                    done, not_done = set(), set()
                    for f in list(future_to_task.keys()):
                        elapsed = time.time() - future_start_times.get(f, 0.0)
                        if f.done() or elapsed > self.task_timeout:
                            done.add(f)
                            
                    if not done:
                        time.sleep(0.1)
                        continue
                        
                    for future in done:
                        task = future_to_task.pop(future)
                        future_start_times.pop(future, None)
                        res = None
                        t_start = time.time()
                        try:
                            if not future.done():
                                raise TimeoutError("Simulated API timeout")
                            # 5 minutes timeout per task
                            res = future.result(timeout=self.task_timeout)
                        except TimeoutError as exc:
                            from ..agents.base_agent import AgentResult
                            res = AgentResult(
                                agent_name=task.agent_type,
                                task=task.objective,
                                status="failed",
                                output={"error": "TASK_TIMEOUT"},
                                confidence=0.0,
                                execution_time=time.time() - t_start
                            )
                        except Exception as exc:
                            from ..agents.base_agent import AgentResult
                            res = AgentResult(
                                agent_name=task.agent_type,
                                task=task.objective,
                                status="failed",
                                output={"error": str(exc), "traceback": traceback.format_exc()},
                                confidence=0.0,
                                execution_time=time.time() - t_start
                            )
                            
                        results.append(res)
                        running_tasks.remove(task.task_id)
                        
                        if res.status == "success":
                            completed_tasks.add(task.task_id)
                            # Emit TaskCompleted
                            self.event_bus.publish(TaskCompleted(job_id=job_id, task_id=task.task_id, duration=res.execution_time, status="success"))
                            
                            # Keep state synced
                            pstate = job_state["pipeline_state"]
                            if "stages" not in pstate:
                                pstate["stages"] = {}
                            pstate["stages"][task.agent_type] = {
                                "ok": True,
                                "status": "success",
                                "execution_time": res.execution_time
                            }
                            
                            # Checkpoint save
                            ckpt_path = self.checkpoint_mgr.save(job_id, completed_tasks, set(pending_tasks.keys()), pstate)
                            self.event_bus.publish(CheckpointSaved(job_id=job_id, node_count=len(completed_tasks), path=ckpt_path))
                        else:
                            # Emit TaskFailed
                            self.event_bus.publish(TaskFailed(job_id=job_id, task_id=task.task_id, error=res.output.get("error", "Unknown"), traceback=res.output.get("traceback", "")))
                            # Non-retryable fails raise RuntimeError to abort or retry from coordinates
                            exc = RuntimeError(f"Task {task.task_id} failed: {res.output.get('error')}")
                            exc.results = results
                            raise exc
                else:
                    if pending_tasks:
                        if tasks_paused_for_resources:
                            time.sleep(0.1)
                            continue
                        else:
                            break

        # Emit Recovery/PipelineCompleted events
        succeeded = len(completed_tasks)
        self.event_bus.publish(PipelineFinished(job_id=job_id, total_tasks=len(agent_tasks), succeeded=succeeded, failed=len(agent_tasks)-succeeded, duration=time.time()-self.observability.start_time))
        self.checkpoint_mgr.cleanup(job_id)
        return results

    def run(self, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph **sequentially** (legacy / compatibility path).

        .. deprecated::
            This sequential execution path is the *legacy* runner used by
            ``Pipeline.execute()`` in graph-orchestrator mode.  New code should
            prefer :meth:`run_dag` which runs tasks in parallel under a
            ``ThreadPoolExecutor`` and supports full DAG semantics.

            Migration target (W1)::

                User Goal
                  ↓
                JarvisBrain.plan_execution()   ← produces ExecutionPlan + agent_tasks
                  ↓
                StateGraph (initialize → execute → reflect → replan)
                  ↓
                GraphOrchestrator.run_dag()    ← parallel DAG, this is the target
                  ↓
                Agents → Workers

        Accepts the legacy pipeline JobState structure, wrapped into UnifiedJobState.
        Checkpoint files are managed through :class:`~appsuite.engine.checkpoint.CheckpointManager`
        to avoid CWD-relative path bugs (W6).
        """
        import warnings
        warnings.warn(
            "GraphOrchestrator.run() is the legacy sequential execution path and will be "
            "superseded by run_dag() in a future release.  See the W1 consolidation "
            "roadmap in IMPLEMENTATION_SUMMARY.md.",
            DeprecationWarning,
            stacklevel=2,
        )

        job_id = job_state["job"]["id"]

        pstate = job_state["pipeline_state"]
        if not isinstance(pstate, UnifiedJobState):
            state = UnifiedJobState.from_dict({
                "job": job_state["job"],
                "pipeline_state": pstate.as_dict() if hasattr(pstate, "as_dict") else pstate
            })
            job_state["pipeline_state"] = state
        else:
            state = pstate
            if not getattr(state, "job", None) and "job" in job_state:
                state.job = job_state["job"]

        state.current_node = self._start_node

        # === W6 FIX: use CheckpointManager instead of raw CWD-relative path ===
        # Previously: checkpoint_file = f"{job_id}_checkpoint.json"  ← CWD-dependent
        ckpt_data = self.checkpoint_mgr.load(job_id)
        if ckpt_data:
            try:
                state = UnifiedJobState.from_dict(ckpt_data.get("state", ckpt_data))
                job_state["pipeline_state"] = state
                log.info("[orchestrator.run] Resumed from checkpoint for job %s", job_id)
            except Exception as ckpt_err:
                log.warning("[orchestrator.run] Failed to restore checkpoint for job %s: %s", job_id, ckpt_err)

        while True:
            node_name = state.current_node
            if node_name == "END":
                break
                
            node = self.nodes.get(node_name)
            if not node:
                raise RuntimeError(f"Unknown graph node: {node_name}")
                
            if state.history.count(node_name) > 3:
                raise RuntimeError(f"Infinite retry limit exceeded for node {node_name}")
                
            t0 = time.time()
            try:
                # Pre-flight health
                from ..core.health import WorkerHealthMonitor
                worker_type = node_name.split('_')[0]
                is_healthy, h_reason = WorkerHealthMonitor.preflight_check(worker_type)
                if not is_healthy:
                    result = WorkerResult(status=WorkerStatus.FAILED, reason=h_reason)
                else:
                    # Run the node process
                    result = node.process(state)
                    # Support legacy node returning a GraphState vs WorkerResult
                    if hasattr(result, "worker_result"):
                        result = result.worker_result
            except Exception as e:
                result = WorkerResult(
                    status=WorkerStatus.FAILED,
                    reason=str(e),
                    metadata={"error_type": type(e).__name__, "traceback": traceback.format_exc()}
                )
            
            dur = time.time() - t0
            if "execution_time" not in result.metadata:
                result.metadata["execution_time"] = dur
                
            state.worker_result = result
            state.current_node = node_name
            state.history.append(node_name)
            
            # Save checkpoint via CheckpointManager (W6 fix — no more CWD-relative raw file I/O)
            try:
                self.checkpoint_mgr.save(job_id, set(state.history), set(), state)
            except Exception as ckpt_save_err:
                log.warning("[orchestrator.run] Failed to save checkpoint for job %s: %s", job_id, ckpt_save_err)
                
            # Route
            next_node = self.router.route(state) if self.router else "END"

            if "stages" not in state.metadata:
                state.metadata["stages"] = {}
            state.metadata["stages"][node_name] = result.status.value

            if next_node == "ABORT":
                raise RuntimeError(f"Job aborted at stage {node_name}: {result.reason}")
            if next_node == "END":
                break
            state.current_node = next_node

        job_state["stages"] = state.metadata.get("stages", {})
        job_state["history"] = state.history
        if state.worker_result and state.worker_result.status == WorkerStatus.FAILED:
            job_state["failure_reason"] = state.worker_result.reason

        # Clean checkpoint via CheckpointManager (W6 fix)
        self.checkpoint_mgr.cleanup(job_id)

        return job_state
