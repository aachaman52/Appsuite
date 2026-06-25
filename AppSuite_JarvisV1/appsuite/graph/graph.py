"""Dynamic Graph Orchestrator Engine."""
from __future__ import annotations
import time
import json
import traceback
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from .state import GraphState
from .nodes import BaseNode
from .router import DecisionNode

class GraphOrchestrator:
    """
    A LangGraph-inspired execution engine supporting node routing and memory passing.
    """
    def __init__(self, db: Any):
        self.db = db
        self.nodes: Dict[str, BaseNode] = {}
        self.router = None
        self._start_node = "asset_search"

    def add_node(self, name: str, node: BaseNode):
        self.nodes[name] = node

    def set_router(self, router: DecisionNode):
        self.router = router

    def run_dag(self, agent_tasks: list, job_state: Dict[str, Any], hardware=None) -> list:
        """
        Executes an AgentTask DAG in parallel. 
        Replaces the AgentCoordinator's ThreadPoolExecutor loop.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor
        from ..agents.base_agent import AgentResult
        
        results = []
        completed_tasks = set()
        running_tasks = set()
        pending_tasks = {t.task_id: t for t in agent_tasks}
        future_to_task = {}
        paused_start_time = {}
        
        # We need a checkpoint file to resume
        job_id = job_state["job"]["id"]
        checkpoint_file = f"{job_id}_dag_checkpoint.json"
        
        import os
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "r") as f:
                    ckpt = json.load(f)
                    completed_tasks = set(ckpt.get("completed", []))
                    # Remove already completed tasks from pending
                    for c_id in completed_tasks:
                        if c_id in pending_tasks:
                            del pending_tasks[c_id]
                    # Restore pipeline_state using GraphState deserialization
                    pstate_data = ckpt.get("pipeline_state")
                    if pstate_data:
                        g_state = GraphState.from_dict({
                            "job": job_state["job"],
                            "pipeline_state": pstate_data
                        })
                        job_state["pipeline_state"] = g_state.pipeline_state
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=4) as executor:
            while pending_tasks or running_tasks:
                tasks_paused_for_resources = False
                
                # Find unblocked tasks
                ready_to_run = []
                for t_id, task in list(pending_tasks.items()):
                    if all(dep in completed_tasks for dep in task.dependencies):
                        ready_to_run.append(task)
                
                # Submit
                for task in ready_to_run:
                    if hardware:
                        res = hardware.resources()
                        if res.get("ram_percent", 0) > 90.0 and task.agent_type == "BlenderAgent":
                            now = time.time()
                            if task.task_id not in paused_start_time:
                                paused_start_time[task.task_id] = now
                            if now - paused_start_time[task.task_id] < 15.0:
                                tasks_paused_for_resources = True
                                continue
                            
                    del pending_tasks[task.task_id]
                    running_tasks.add(task.task_id)
                    
                    if task.agent_type in self.nodes:
                        agent_node = self.nodes[task.agent_type]
                        # Inject job_state into agent
                        agent_node.current_job_state = job_state
                        
                        future = executor.submit(agent_node.run, task)
                        future_to_task[future] = task
                    else:
                        completed_tasks.add(task.task_id)
                        running_tasks.remove(task.task_id)
                
                if running_tasks:
                    done, _ = set(), set()
                    for f in list(future_to_task.keys()):
                        if f.done():
                            done.add(f)
                            
                    if not done:
                        time.sleep(0.1)
                        continue
                        
                    for future in done:
                        task = future_to_task.pop(future)
                        res = None
                        try:
                            res = future.result()
                            results.append(res)
                        except Exception as exc:
                            res = AgentResult(
                                agent_name=task.agent_type,
                                task=task.task_id,
                                status="failed",
                                output={"error": str(exc)},
                                confidence=0.0,
                                execution_time=0.0
                            )
                            results.append(res)
                        
                        # Save execution stage status to pipeline_state
                        if "pipeline_state" in job_state:
                            if "stages" not in job_state["pipeline_state"]:
                                job_state["pipeline_state"]["stages"] = {}
                            job_state["pipeline_state"]["stages"][task.agent_type] = {
                                "ok": res.status == "success",
                                "status": res.status,
                                "execution_time": getattr(res, "execution_time", 0.0)
                            }
                        
                        running_tasks.remove(task.task_id)
                        if res.status == "success":
                            completed_tasks.add(task.task_id)
                            # Save checkpoint only on successful tasks to prevent skipping failures on retry
                            try:
                                g_state = GraphState(job=job_state["job"], pipeline_state=job_state["pipeline_state"])
                                ckpt_data = {
                                    "completed": list(completed_tasks),
                                    "pipeline_state": g_state.to_dict()["pipeline_state"]
                                }
                                with open(checkpoint_file, "w") as f:
                                    json.dump(ckpt_data, f)
                            except Exception:
                                pass
                else:
                    if pending_tasks:
                        if tasks_paused_for_resources:
                            time.sleep(0.1)
                            continue
                        else:
                            break

        return results

    def run(self, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the graph to completion.
        Accepts the legacy pipeline JobState structure.
        """
        # Build initial graph state
        state = GraphState(
            job=job_state["job"],
            pipeline_state=job_state["pipeline_state"],
            current_node=self._start_node,
        )
        
        job_id = state.job["id"]
        # Output directory is assumed to be available or we can just use the DB to store it?
        # A simpler checkpoint is writing to the project output dir, but we don't have direct access here.
        # We can store it in the current working directory as a temporary fallback, or pass it in.
        # We'll use a local json file as requested.
        checkpoint_file = f"{job_id}_checkpoint.json"
        
        if hasattr(self, 'db') and self.db:
            # Load checkpoint if it exists
            import os
            if os.path.exists(checkpoint_file):
                try:
                    with open(checkpoint_file, "r") as f:
                        ckpt_data = json.load(f)
                    
                    state = GraphState.from_dict(ckpt_data)
                    # We must restore the pipeline_state reference back to job_state so it stays synced
                    job_state["pipeline_state"] = state.pipeline_state
                    self.db.add_event(job_id, f"Resuming execution from checkpoint at node {state.current_node}", level="info")
                except Exception as e:
                    self.db.add_event(job_id, f"Failed to load checkpoint: {e}", level="warning")

        while True:
            node_name = state.current_node
            
            if node_name == "END":
                break
                
            if node_name not in self.nodes:
                if self.db:
                    self.db.add_event(state.job["id"], f"Node {node_name} not found in graph!", level="error")
                raise RuntimeError(f"Unknown graph node: {node_name}")
                
            node = self.nodes[node_name]
            
            if self.db:
                self.db.add_event(state.job["id"], f"Stage start: {node_name}", stage=node_name)
                
            # Infinite retry protection
            if state.history.count(node_name) > 3:
                if self.db:
                    self.db.add_event(state.job["id"], f"Infinite retry protection triggered for {node_name}", level="error")
                raise RuntimeError(f"Infinite retry limit exceeded for node {node_name}")
                
            # Execute node with timeout
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(node.process, state)
                    # 5 minutes max timeout per node
                    state = future.result(timeout=300)
            except TimeoutError:
                from ..core.state import WorkerResult, WorkerStatus
                state.worker_result = WorkerResult(
                    status=WorkerStatus.FAILED,
                    reason="NODE_TIMEOUT",
                    metadata={"error_type": "TimeoutError"}
                )
            except Exception as e:
                from ..core.state import WorkerResult, WorkerStatus
                state.worker_result = WorkerResult(
                    status=WorkerStatus.FAILED,
                    reason=f"CRASH: {str(e)}",
                    metadata={"error_type": type(e).__name__, "traceback": traceback.format_exc()}
                )
            
            res = state.worker_result
            if self.db and res:
                self.db.add_event(
                    state.job["id"],
                    f"Stage done: {node_name} in {res.metadata.get('execution_time', 0):.3f}s status={res.status.value}",
                    stage=node_name
                )
                
            # Checkpoint save
            try:
                with open(checkpoint_file, "w") as f:
                    json.dump(state.to_dict(), f)
            except Exception:
                pass
                
            # Route
            next_node = self.router.route(state)
            
            # Record stage result safely in metadata
            if res:
                if "stages" not in state.metadata:
                    state.metadata["stages"] = {}
                state.metadata["stages"][node_name] = res.status.value
            
            if next_node == "ABORT":
                reason = res.reason if res else "Unknown"
                raise RuntimeError(f"Supervisor aborted job at stage {node_name}: {reason}")
            
            if next_node == "END":
                break
                
            state.current_node = next_node

        # Dump graph execution metadata back to job dictionary summary
        job_state["stages"] = state.metadata.get("stages", {})
        job_state["history"] = state.history
        if state.worker_result and state.worker_result.status.value == "failed":
            job_state["failure_reason"] = state.worker_result.reason
        return job_state
