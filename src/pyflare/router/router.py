"""Deterministic Route Planner for PyFlare."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pyflare.core.hardware_manager import HardwareManager
from pyflare.router.capability_registry import CapabilityRegistry
from pyflare.router.history import RouterHistoryTracker
from pyflare.router.models import (
    HardwareProfile,
    RouteCandidate,
    RouteDecision,
    TaskSpec,
    TaskType,
)
from pyflare.router.scoring import ScoringWeights, filter_candidate, score_candidate


class DeterministicRouter:
    """
    Evaluates execution requests, hardware constraints, and provider capabilities
    to produce a deterministic primary route and ordered fallbacks.
    """

    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        hardware_manager: Optional[HardwareManager] = None,
        history_tracker: Optional[RouterHistoryTracker] = None,
        weights: Optional[ScoringWeights] = None,
    ) -> None:
        self.registry = registry or CapabilityRegistry()
        self.hardware_manager = hardware_manager or HardwareManager({})
        self.history_tracker = history_tracker or RouterHistoryTracker()
        self.weights = weights or ScoringWeights()

    def plan_route(self, task: TaskSpec) -> RouteDecision:
        """
        Evaluate all candidates against task constraints and return a deterministic RouteDecision.
        Never calls an LLM or non-deterministic heuristic.
        """
        hardware_profile: HardwareProfile = self.hardware_manager.get_hardware_profile()
        all_candidates = self.registry.list_candidates()

        accepted: List[RouteCandidate] = []
        rejected: Dict[str, str] = {}
        scores: Dict[str, float] = {}
        candidate_rationales: Dict[str, List[str]] = {}

        # 1. Filter candidates
        for candidate in all_candidates:
            is_valid, reason = filter_candidate(candidate, task, hardware_profile)
            if is_valid:
                accepted.append(candidate)
            else:
                rejected[candidate.candidate_id] = reason or "Constraint violation"

        # 2. Score accepted candidates
        for candidate in accepted:
            hist_stats = self.history_tracker.get_candidate_stats(candidate.candidate_id, task.task_type)
            score, reasons = score_candidate(candidate, task, hardware_profile, hist_stats, self.weights)
            scores[candidate.candidate_id] = score
            candidate_rationales[candidate.candidate_id] = reasons

        # 3. Sort deterministically
        if task.task_type == TaskType.THREE_D_GENERATION:
            def _3d_policy_tier(cand: RouteCandidate) -> int:
                if cand.candidate_id == "meshy-3d":
                    return 1
                elif cand.candidate_id == "local-3d-model":
                    return 2
                elif cand.candidate_id == "blender-worker":
                    return 3
                return 4

            ranked_candidates = sorted(
                accepted,
                key=lambda c: (_3d_policy_tier(c), -scores.get(c.candidate_id, 0.0), c.candidate_id)
            )
        else:
            ranked_candidates = sorted(
                accepted,
                key=lambda c: (-scores.get(c.candidate_id, 0.0), c.candidate_id)
            )

        selected: Optional[RouteCandidate] = ranked_candidates[0] if ranked_candidates else None
        fallbacks: List[RouteCandidate] = ranked_candidates[1:] if len(ranked_candidates) > 1 else []

        # 4. Formulate selection rationale
        selection_reasons: List[str] = []
        if selected:
            selection_reasons.append(f"Selected '{selected.display_name}' with highest deterministic score {scores[selected.candidate_id]:.4f}")
            selection_reasons.extend(candidate_rationales.get(selected.candidate_id, []))
        else:
            selection_reasons.append("No candidate satisfied the task execution constraints and hardware requirements.")
            if task.task_type == TaskType.THREE_D_GENERATION:
                selection_reasons.append("3D Policy Diagnostic: No 3D pipeline available. To enable 3D generation: (1) Set MESHY_API_KEY for cloud 3D, (2) Install Blender in PATH for local mesh scripts, or (3) Install a local neural 3D model with sufficient VRAM.")

        est_cost = selected.estimated_cost_usd if selected else 0.0
        est_lat = selected.expected_latency_seconds if selected else 0.0

        return RouteDecision(
            task_id=task.task_id,
            selected_candidate=selected,
            score=scores.get(selected.candidate_id, 0.0) if selected else 0.0,
            selection_reasons=selection_reasons,
            fallback_candidates=fallbacks,
            accepted_candidates=accepted,
            rejected_candidates=rejected,
            candidate_scores=scores,
            estimated_cost_usd=est_cost,
            estimated_latency_seconds=est_lat,
            hardware_profile_summary=hardware_profile.model_dump(),
        )
