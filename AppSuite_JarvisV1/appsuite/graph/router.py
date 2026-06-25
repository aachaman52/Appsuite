"""Graph Router (Decision Node) logic."""
from __future__ import annotations
from typing import Any

from .state import GraphState
from ..core.supervisor import Supervisor, SupervisorAction

class DecisionNode:
    """
    Wraps the existing Supervisor logic.
    Instead of simply returning an Action, it determines the NEXT node to visit.
    """
    def __init__(self, supervisor: Supervisor):
        self.supervisor = supervisor

    def route(self, state: GraphState) -> str:
        if not state.worker_result:
            return "END"

        job_id = state.job["id"]
        stage_name = state.current_node

        # Let existing supervisor process the result
        action = self.supervisor.handle_result(job_id, stage_name, state.worker_result)

        if action == SupervisorAction.ABORT:
            return "ABORT"
            
        # Explicitly handle NEED_ASSET BEFORE linear proceed routing
        if state.worker_result and state.worker_result.status.name == "NEED_ASSET":
            return "asset_search"
            
        if action == SupervisorAction.RETRY:
            return stage_name # Route back to self!
        elif action == SupervisorAction.CHANGE_PROVIDER:
            # We treat this as a retry on self, Supervisor already changed the provider
            return stage_name
        elif action == SupervisorAction.PROCEED:
            # Determine the logical next step based on the CURRENT node
            # This replaces the hardcoded TRANSITIONS loop
            if stage_name == "asset_search":
                return "asset_processing"
            elif stage_name == "asset_processing":
                return "blender_import"
            elif stage_name == "blender_import":
                return "godot_import"
            elif stage_name == "godot_import":
                return "output_validation"
            elif stage_name == "output_validation":
                return "cloud_deploy"
            elif stage_name == "cloud_deploy":
                return "END"
        
        return "END"
