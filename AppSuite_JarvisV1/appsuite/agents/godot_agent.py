"""GodotAgent — drives Godot scene construction, validation, and deployment stages.

Thread safety note
------------------
``execute_tools`` receives ``job_state`` as an explicit parameter rather than
reading it from ``self.current_job_state``.  This means the same agent instance
can be called concurrently from multiple ``ThreadPoolExecutor`` threads without
any shared mutable state between invocations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, AgentTask

from ..logging_setup import get_logger

log = get_logger("agents.godot")


class GodotAgent(BaseAgent):
    """Agent responsible for Godot import, scene building, and cloud deploy stages."""

    def receive_task(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> None:
        log.info("[%s] Building scene for: %s", self.name, task.objective)
        if self.message_bus:
            self.message_bus.send("godot_status", "Building scene...")

    def plan(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> List[str]:
        """Return the ordered pipeline nodes this agent will execute."""
        return ["godot_import", "output_validation", "cloud_deploy"]

    def execute_tools(self, plan: Any, job_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute Godot pipeline nodes using the isolated ``job_state`` passed in.

        Parameters
        ----------
        plan      : Ordered list of node names to execute.
        job_state : Isolated per-invocation state ``{"job": ..., "pipeline_state": ...}``.
                    Must NOT be stored on ``self`` — each thread call receives its own copy.
        """
        if self.message_bus:
            self.message_bus.send("godot_status", "Executing godot nodes")

        exec_results: List[Dict[str, Any]] = []

        if not job_state:
            log.warning("[%s] execute_tools called with no job_state — skipping execution", self.name)
            return {"execution_results": exec_results}

        job = job_state["job"]
        pstate = job_state["pipeline_state"]

        for node_name in plan:
            worker_key = self.dynamic_route_worker(node_name, job_state)
            if worker_key and worker_key in self.workers:
                worker = self.workers[worker_key]
                if hasattr(worker, "health_check"):
                    res = worker.process(job, pstate)
                else:
                    from ..core.health import WorkerHealthMonitor
                    is_healthy, h_reason = WorkerHealthMonitor.preflight_check(worker_key)
                    if not is_healthy:
                        raise RuntimeError(f"Health check failed for {worker_key}: {h_reason}")
                    res = worker.process(job, pstate)

                status_val = res.status.value
                exec_results.append({node_name: status_val})
                if status_val == "failed":
                    if "Health check failed" in res.reason:
                        raise RuntimeError(f"Health check failed for {worker_key}: {res.reason}")
                    raise RuntimeError(f"{node_name} failed: {res.reason}")

            elif self.orchestrator and node_name in self.orchestrator.nodes:
                node = self.orchestrator.nodes[node_name]
                from ..graph.state import GraphState
                g_state = GraphState(job=job, pipeline_state=pstate, current_node=node_name)
                res_state = node.process(g_state)
                status_val = res_state.worker_result.status.value
                exec_results.append({node_name: status_val})
                if status_val == "failed":
                    raise RuntimeError(f"{node_name} failed: {res_state.worker_result.reason}")

        return {"execution_results": exec_results}
