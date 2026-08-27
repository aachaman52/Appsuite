"""Deterministic scoring algorithms and weight definitions for PyFlare Router."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from pyflare.router.models import (
    HardwareProfile,
    HardwareTier,
    PrivacyLevel,
    RouteCandidate,
    TaskSpec,
    TaskType,
)


class ScoringWeights(BaseModel):
    """Configurable weights for deterministic route scoring."""
    capability_match: float = 0.20
    task_relevance: float = 0.15
    historical_success: float = 0.15
    quality: float = 0.15
    latency: float = 0.10
    cost: float = 0.10
    hardware_suitability: float = 0.10
    privacy_bonus: float = 0.05


def filter_candidate(
    candidate: RouteCandidate,
    task: TaskSpec,
    hardware: HardwareProfile,
) -> Tuple[bool, Optional[str]]:
    """
    Check all hard constraints. Returns (is_accepted, rejection_reason).
    Pure deterministic function.
    """
    # 1. Check availability
    if not candidate.is_available:
        return False, candidate.unavailability_reason or "Candidate marked unavailable"

    # 2. Check supported task types
    if candidate.supported_task_types:
        domain_specific = {
            TaskType.THREE_D_GENERATION,
            TaskType.IMAGE_GENERATION,
            TaskType.GODOT_AUTOMATION,
            TaskType.BLENDER_AUTOMATION,
            TaskType.DEPLOYMENT,
        }
        if task.task_type in domain_specific:
            if task.task_type not in candidate.supported_task_types:
                t_name = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
                return False, f"Candidate does not support domain-specific task type '{t_name}'"
        else:
            if task.task_type not in candidate.supported_task_types and TaskType.GENERAL not in candidate.supported_task_types:
                t_name = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
                return False, f"Candidate does not support task type '{t_name}'"

    # 3. Cloud and local restrictions
    if not task.allow_cloud and not candidate.is_local:
        return False, "Cloud processing disallowed by task specification"
    if task.require_local and not candidate.is_local:
        return False, "Local execution required by task specification"

    # 3. Privacy level conformance
    privacy_order = {PrivacyLevel.PUBLIC: 0, PrivacyLevel.INTERNAL: 1, PrivacyLevel.CONFIDENTIAL: 2}
    if privacy_order.get(candidate.privacy_level, 0) < privacy_order.get(task.privacy_level, 1):
        return False, f"Candidate privacy level '{candidate.privacy_level}' does not satisfy required '{task.privacy_level}'"

    # 4. Required task capabilities
    candidate_cap_names = {c.capability_name: c.level for c in candidate.capabilities}
    for req in task.required_capabilities:
        if req not in candidate_cap_names:
            return False, f"Candidate missing required capability: '{req}'"

    # 5. Required tools / binaries
    if candidate.required_executable:
        if not hardware.installed_binaries.get(candidate.required_executable, False):
            return False, f"Required executable '{candidate.required_executable}' is not installed"

    # 6. Hardware resource limits (RAM & VRAM)
    if candidate.min_ram_mb > hardware.ram_available_mb:
        return False, f"Insufficient available RAM: candidate requires {candidate.min_ram_mb}MB (available: {hardware.ram_available_mb:.1f}MB)"
    if candidate.min_vram_mb > 0 and candidate.min_vram_mb > hardware.vram_available_mb:
        return False, f"Insufficient available VRAM: candidate requires {candidate.min_vram_mb}MB (available: {hardware.vram_available_mb:.1f}MB)"

    # 7. Cost limit
    if task.max_cost_usd is not None and candidate.estimated_cost_usd > task.max_cost_usd:
        return False, f"Estimated cost ${candidate.estimated_cost_usd:.4f} exceeds max allowed ${task.max_cost_usd:.4f}"

    # 8. Minimum quality score
    if candidate.quality_score < task.min_quality_score:
        return False, f"Quality score {candidate.quality_score:.2f} below required minimum {task.min_quality_score:.2f}"

    return True, None


def score_candidate(
    candidate: RouteCandidate,
    task: TaskSpec,
    hardware: HardwareProfile,
    history_stats: Dict[str, Any],
    weights: Optional[ScoringWeights] = None,
) -> Tuple[float, List[str]]:
    """
    Compute a deterministic composite score (0.0 to 1.0) and explanatory rationale.
    Does NOT invoke any AI or external services.
    """
    w = weights or ScoringWeights()
    reasons: List[str] = []

    # 1. Capability match score (0.0 - 1.0)
    candidate_caps = {c.capability_name: c.level for c in candidate.capabilities}
    if task.required_capabilities:
        match_sum = sum(candidate_caps.get(req, 0.0) for req in task.required_capabilities)
        cap_score = match_sum / len(task.required_capabilities)
    else:
        cap_score = 0.90
    reasons.append(f"Capability match: {cap_score:.2f}")

    # 2. Task relevance score (0.0 - 1.0)
    if task.task_type in candidate.supported_task_types:
        relevance_score = 1.0
    elif TaskType.GENERAL in candidate.supported_task_types:
        relevance_score = 0.70
    else:
        relevance_score = 0.50
    reasons.append(f"Task relevance: {relevance_score:.2f}")

    # 3. Historical success score (0.0 - 1.0)
    hist_score = float(history_stats.get("smoothed_success_rate", 0.85))
    samples = history_stats.get("sample_count", 0)
    reasons.append(f"Historical success: {hist_score:.2f} ({samples} samples)")

    # 4. Quality score (0.0 - 1.0)
    quality_score = float(candidate.quality_score)
    reasons.append(f"Base quality: {quality_score:.2f}")

    # 5. Latency score (0.0 - 1.0)
    # Higher score for lower latency
    lat = max(0.01, candidate.expected_latency_seconds)
    latency_score = 1.0 / (1.0 + (lat / 5.0))
    if task.preferred_latency_seconds and lat <= task.preferred_latency_seconds:
        latency_score = min(1.0, latency_score * 1.15)
    reasons.append(f"Latency score: {latency_score:.2f} (~{lat:.1f}s)")

    # 6. Cost score (0.0 - 1.0)
    # Higher score for lower cost
    cost = candidate.estimated_cost_usd
    cost_score = 1.0 / (1.0 + (cost * 50.0))
    reasons.append(f"Cost score: {cost_score:.2f} (~${cost:.4f})")

    # 7. Hardware suitability score (0.0 - 1.0)
    if candidate.is_local:
        if hardware.hardware_tier == HardwareTier.HIGH:
            hw_score = 1.0
        elif hardware.hardware_tier == HardwareTier.MID:
            hw_score = 0.85
        else:
            hw_score = 0.65
    else:
        # Cloud candidates are light on host hardware
        hw_score = 0.95
    reasons.append(f"Hardware suitability: {hw_score:.2f} ({hardware.hardware_tier.value} tier)")

    # 8. Privacy score
    if candidate.is_local or candidate.privacy_level == PrivacyLevel.CONFIDENTIAL:
        privacy_score = 1.0
    else:
        privacy_score = 0.80

    total_score = (
        cap_score * w.capability_match +
        relevance_score * w.task_relevance +
        hist_score * w.historical_success +
        quality_score * w.quality +
        latency_score * w.latency +
        cost_score * w.cost +
        hw_score * w.hardware_suitability +
        privacy_score * w.privacy_bonus
    )

    return round(total_score, 4), reasons
