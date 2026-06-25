"""Jarvis Brain - Intelligent Orchestrator Decision Layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .hardware_manager import HardwareManager
from .provider_manager import ProviderManager
from .semantic_memory import SemanticMemory
from .token_banker import TokenBanker


@dataclass
class ExecutionPlan:
    stages: List[str]
    reasoning: str
    reused_assets: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_tasks: List[Any] = field(default_factory=list) # List of AgentTask
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stages": self.stages,
            "reasoning": self.reasoning,
            "reused_assets": self.reused_assets,
            "metadata": self.metadata,
            "agent_tasks": [t.__dict__ for t in self.agent_tasks] if self.agent_tasks else []
        }


class JarvisBrain:
    """Intelligent decision layer replacing the static planner."""

    def __init__(
        self,
        semantic_memory: SemanticMemory,
        provider_manager: ProviderManager,
        token_banker: TokenBanker,
        hardware_manager: HardwareManager,
        templates: Any
    ):
        self.memory = semantic_memory
        self.providers = provider_manager
        self.banker = token_banker
        self.hardware = hardware_manager
        self.templates = templates

    def plan_execution(self, prompt: str, template_id: Optional[str] = None) -> ExecutionPlan:
        """Analyze the job and generate an optimal execution plan."""
        
        # 1. Check Semantic Memory for previous successes
        similar_job = self.memory.recall_similar(prompt, threshold=0.7)
        
        from ..agents.base_agent import AgentTask
        
        # Phase 6.5: Generate Dependency Graph of AgentTask
        agent_tasks = []
        
        if similar_job and similar_job.get("outcome") == "success":
            # Reusing assets means no AssetAgent needed
            t1 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize cached models", priority=1)
            t2 = AgentTask(task_id="code_1", agent_type="CodeAgent", objective="Generate scripts", priority=2)
            t3 = AgentTask(task_id="godot_1", agent_type="GodotAgent", objective="Build scene", dependencies=["blender_1", "code_1"], priority=1)
            agent_tasks.extend([t1, t2, t3])
            
            return ExecutionPlan(
                stages=["asset_processing", "blender_import", "godot_import", "output_validation", "cloud_deploy"],
                agent_tasks=agent_tasks,
                reasoning=f"Found high-confidence semantic match (score {similar_job.get('similarity_score', 0):.2f}) from job {similar_job.get('job_id')}. Reusing assets and bypassing search.",
                reused_assets=True,
                metadata={"matched_job": similar_job.get("job_id")}
            )
            
        # 2. Hardware Resource Check
        res = self.hardware.resources()
        if res.get("ram_percent", 0) > 90.0:
            # We will still schedule the job, but the pipeline/hardware manager might pause workers
            reasoning = "Standard pipeline scheduled, but RAM is critically high. Heavy workers may be delayed."
        else:
            reasoning = "Standard pipeline scheduled. Full asset acquisition planned."
            
        t1 = AgentTask(task_id="asset_1", agent_type="AssetAgent", objective="Find and process assets", priority=1)
        t2 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize models", dependencies=["asset_1"], priority=2)
        t3 = AgentTask(task_id="code_1", agent_type="CodeAgent", objective="Generate scripts", priority=3)
        t4 = AgentTask(task_id="godot_1", agent_type="GodotAgent", objective="Build scene", dependencies=["blender_1", "code_1"], priority=1)
        agent_tasks.extend([t1, t2, t3, t4])
            
        return ExecutionPlan(
            stages=["asset_search", "asset_processing", "blender_import", "godot_import", "output_validation", "cloud_deploy"],
            agent_tasks=agent_tasks,
            reasoning=reasoning,
            reused_assets=False
        )
