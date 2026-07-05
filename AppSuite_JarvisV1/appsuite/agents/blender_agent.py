from __future__ import annotations
from typing import Any, Dict
from .base_agent import BaseAgent, AgentTask

class BlenderAgent(BaseAgent):
    def receive_task(self, task: AgentTask):
        print(f"[{self.name}] Optimizing models")
        if self.message_bus:
            self.message_bus.send("blender_status", "Optimizing models...")

    def plan(self, task: AgentTask) -> Any:
        return ["blender_import"]

    def execute_tools(self, plan: Any) -> Any:
        if self.message_bus:
            self.message_bus.send("blender_status", "Executing blender nodes")
            
        exec_results = []
        if hasattr(self, 'current_job_state'):
            job_state = self.current_job_state
            job = job_state["job"]
            pstate = job_state["pipeline_state"]
            
            worker_map = {
                "blender_import": "blender"
            }
            
            for node_name in plan:
                worker_key = worker_map.get(node_name)
                if worker_key and worker_key in self.workers:
                    worker = self.workers[worker_key]
                    if hasattr(worker, "health_check"):
                        res = worker.process(job, pstate)
                        status_val = res.status.value
                        exec_results.append({node_name: status_val})
                        if status_val == "failed":
                            if "Health check failed" in res.reason:
                                h_reason = res.reason.replace("Health check failed: ", "").replace("Health check & Recovery failed: ", "")
                                raise RuntimeError(f"Health check failed for {worker_key}: {h_reason}")
                            raise RuntimeError(f"{node_name} failed: {res.reason}")
                    else:
                        from ..core.health import WorkerHealthMonitor
                        is_healthy, h_reason = WorkerHealthMonitor.preflight_check(worker_key)
                        if not is_healthy:
                            raise RuntimeError(f"Health check failed for {worker_key}: {h_reason}")
                        res = worker.process(job, pstate)
                        status_val = res.status.value
                        exec_results.append({node_name: status_val})
                        if status_val == "failed":
                            raise RuntimeError(f"{node_name} failed: {res.reason}")
                else:
                    if self.orchestrator and node_name in self.orchestrator.nodes:
                        node = self.orchestrator.nodes[node_name]
                        from ..graph.state import GraphState
                        g_state = GraphState(job=job, pipeline_state=pstate, current_node=node_name)
                        res_state = node.process(g_state)
                        status_val = res_state.worker_result.status.value
                        exec_results.append({node_name: status_val})
                        if status_val == "failed":
                            raise RuntimeError(f"{node_name} failed: {res_state.worker_result.reason}")
                            
        return {"execution_results": exec_results}
