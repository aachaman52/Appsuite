from __future__ import annotations
from typing import Any, Dict
from .base_agent import BaseAgent, AgentTask

class AssetAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def receive_task(self, task: AgentTask):
        print(f"[{self.name}] Finding assets")
        if self.message_bus:
            self.message_bus.send("asset_status", "Finding assets...")

    def plan(self, task: AgentTask) -> Any:
        return ["asset_search", "asset_processing"]

    def execute_tools(self, plan: Any) -> Any:
        if self.message_bus:
            self.message_bus.send("asset_status", "Executing asset nodes")
        
        exec_results = []
        if self.orchestrator and hasattr(self, 'current_job_state'):
            from ..graph.state import GraphState
            job_state = self.current_job_state
            
            for node_name in plan:
                if node_name in self.orchestrator.nodes:
                    node = self.orchestrator.nodes[node_name]
                    g_state = GraphState(
                        job=job_state["job"], 
                        pipeline_state=job_state.get("pipeline_state", {}), 
                        current_node=node_name
                    )
                    res_state = node.process(g_state)
                    status_val = res_state.worker_result.status.value
                    exec_results.append({node_name: status_val})
                    if status_val == "failed":
                        raise RuntimeError(f"{node_name} failed: {res_state.worker_result.reason}")
                        
        return {"execution_results": exec_results}
