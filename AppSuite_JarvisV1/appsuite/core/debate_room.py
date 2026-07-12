"""
Debate Room - Phase 2 Intelligence
==================================
Specialist planners propose competing execution strategies.
The Supervisor evaluates the proposals and selects the best plan.

Agents:
- PlannerAgent: Focuses on standard pipeline flow.
- AssetAgent: Focuses on asset quality and sourcing.
- CodeAgent: Focuses on code/logic generation.
- GameDesignAgent: Focuses on scene composition and gameplay.
- ReliabilityAgent: Focuses on safe fallbacks and risk mitigation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_setup import get_logger

log = get_logger("supervisor.debate_room")

@dataclass
class StrategyProposal:
    agent_name: str
    template_id: str
    worker_sequence: List[str]
    asset_hints: Dict[str, str]
    reasoning: str
    confidence: float
    vote_score: float = 0.0


class BaseDebateAgent:
    def __init__(self, name: str):
        self.name = name

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        raise NotImplementedError


class PlannerAgent(BaseDebateAgent):
    def __init__(self):
        super().__init__("PlannerAgent")

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        # Standard balanced pipeline
        workers = ["internet", "analysis", "godot", "validation"]
        template = "generic_scene"
        if memory_ctx.similar_successes:
            template = memory_ctx.similar_successes[0].get("template_id", "generic_scene")
        
        reasoning = "Standard sequential pipeline is balanced for general tasks."
        if memory_ctx.recommended_strategy:
            combo = memory_ctx.recommended_strategy.get("strategy", {}).get("worker_combination")
            if combo:
                workers = combo
                reasoning = "Using historically proven worker sequence."

        return StrategyProposal(
            agent_name=self.name,
            template_id=template,
            worker_sequence=workers,
            asset_hints=memory_ctx.best_assets,
            reasoning=reasoning,
            confidence=0.8
        )


class AssetAgent(BaseDebateAgent):
    def __init__(self):
        super().__init__("AssetAgent")

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        # Focus heavily on Blender if 3D keywords present
        pl = prompt.lower()
        workers = ["internet", "analysis"]
        if any(k in pl for k in ("3d", "mesh", "blender", "model", "fbx", "glb")):
            workers.append("blender")
        workers.append("godot")
        
        reasoning = "Prioritizing asset processing and validation."
        return StrategyProposal(
            agent_name=self.name,
            template_id="generic_scene",
            worker_sequence=workers,
            asset_hints=memory_ctx.best_assets,
            reasoning=reasoning,
            confidence=0.85 if memory_ctx.best_assets else 0.6
        )


class CodeAgent(BaseDebateAgent):
    def __init__(self):
        super().__init__("CodeAgent")

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        # Include code worker if script logic is mentioned
        pl = prompt.lower()
        workers = ["internet", "analysis", "godot"]
        if any(k in pl for k in ("script", "code", "logic", "mechanic", "player", "enemy")):
            workers.insert(2, "code")
        
        return StrategyProposal(
            agent_name=self.name,
            template_id="generic_scene",
            worker_sequence=workers,
            asset_hints=memory_ctx.best_assets,
            reasoning="Added CodeWorker for logic implementation.",
            confidence=0.75
        )


class GameDesignAgent(BaseDebateAgent):
    def __init__(self):
        super().__init__("GameDesignAgent")

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        pl = prompt.lower()
        template = "generic_scene"
        if "fps" in pl:
            template = "fps_level"
        elif "rpg" in pl:
            template = "rpg_level"
        elif "platformer" in pl:
            template = "platformer"
            
        workers = ["internet", "analysis", "godot", "validation"]
        return StrategyProposal(
            agent_name=self.name,
            template_id=template,
            worker_sequence=workers,
            asset_hints=memory_ctx.best_assets,
            reasoning=f"Selected {template} template for optimal game design.",
            confidence=0.9 if template != "generic_scene" else 0.5
        )


class ReliabilityAgent(BaseDebateAgent):
    def __init__(self):
        super().__init__("ReliabilityAgent")

    def propose(self, prompt: str, memory_ctx: Any, risks: List[str]) -> StrategyProposal:
        # Minimal safe pipeline
        workers = ["internet", "godot"]
        template = "generic_scene"
        reasoning = "Stripped pipeline down to essentials to minimize points of failure."
        confidence = 0.9 if len(risks) > 2 else 0.4
        
        return StrategyProposal(
            agent_name=self.name,
            template_id=template,
            worker_sequence=workers,
            asset_hints=memory_ctx.best_assets,
            reasoning=reasoning,
            confidence=confidence
        )


class DebateRoom:
    def __init__(self, db=None):
        self.db = db
        self.agents = [
            PlannerAgent(),
            AssetAgent(),
            CodeAgent(),
            GameDesignAgent(),
            ReliabilityAgent()
        ]

    def hold_debate(self, prompt: str, memory_ctx: Any, risks: List[str], job_id: str) -> StrategyProposal:
        proposals: List[StrategyProposal] = []
        
        for agent in self.agents:
            try:
                proposal = agent.propose(prompt, memory_ctx, risks)
                proposals.append(proposal)
            except Exception as exc:
                log.warning("DebateRoom: %s failed to propose - %s", agent.name, exc)

        if not proposals:
            # Fallback
            return StrategyProposal(
                agent_name="Fallback",
                template_id="generic_scene",
                worker_sequence=["internet", "analysis", "godot"],
                asset_hints={},
                reasoning="Emergency fallback",
                confidence=0.1,
                vote_score=1.0
            )

        # Scoring logic
        # 1. Base score is agent's self-reported confidence
        # 2. Add consensus bonus: if multiple agents propose the same template/workers
        for p in proposals:
            p.vote_score = p.confidence
            
            # Consensus on worker sequence
            same_workers = sum(1 for other in proposals if other.worker_sequence == p.worker_sequence)
            p.vote_score += (same_workers - 1) * 0.1
            
            # Consensus on template
            same_template = sum(1 for other in proposals if other.template_id == p.template_id)
            p.vote_score += (same_template - 1) * 0.05
            
            # Risk penalty for heavy pipelines if risks are high
            if len(risks) > 1 and len(p.worker_sequence) > 3:
                p.vote_score -= 0.15

        # Select best
        proposals.sort(key=lambda x: x.vote_score, reverse=True)
        winner = proposals[0]

        log.info("[%s] Debate concluded. Winner: %s (score: %.2f)", job_id[:8], winner.agent_name, winner.vote_score)
        
        # Log to db timeline
        if self.db:
            try:
                self.db.add_event(
                    job_id,
                    f"[DEBATE] Winner: {winner.agent_name} | Score: {winner.vote_score:.2f} | Reasoning: {winner.reasoning}",
                    stage="planning",
                    level="info"
                )
            except Exception:
                pass

        return winner
