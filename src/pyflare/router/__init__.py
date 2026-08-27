"""Deterministic Routing Layer for PyFlare."""
from pyflare.router.adapters import (
    AdapterUnavailableError,
    ExecutionTimeoutError,
    create_blender_worker_adapter,
    create_code_worker_adapter,
    create_godot_worker_adapter,
    create_provider_manager_adapter,
    create_rule_engine_adapter,
    create_validation_worker_adapter,
)
from pyflare.router.capability_registry import CapabilityRegistry
from pyflare.router.executor import (
    CandidateExecutionAttempt,
    RouteExecutionResult,
    RouterExecutor,
)
from pyflare.router.history import RouterHistoryTracker
from pyflare.router.models import (
    CapabilityRequirement,
    ExecutionConstraint,
    HardwareProfile,
    HardwareTier,
    PrivacyLevel,
    ProviderCapability,
    RouteCandidate,
    RouteDecision,
    RouteOutcome,
    TaskSpec,
    TaskType,
)
from pyflare.router.router import DeterministicRouter
from pyflare.router.scoring import ScoringWeights, filter_candidate, score_candidate

__all__ = [
    "AdapterUnavailableError",
    "CapabilityRegistry",
    "CapabilityRequirement",
    "CandidateExecutionAttempt",
    "DeterministicRouter",
    "ExecutionConstraint",
    "ExecutionTimeoutError",
    "HardwareProfile",
    "HardwareTier",
    "PrivacyLevel",
    "ProviderCapability",
    "RouteCandidate",
    "RouteDecision",
    "RouteExecutionResult",
    "RouteOutcome",
    "RouterExecutor",
    "RouterHistoryTracker",
    "ScoringWeights",
    "TaskSpec",
    "TaskType",
    "create_blender_worker_adapter",
    "create_code_worker_adapter",
    "create_godot_worker_adapter",
    "create_provider_manager_adapter",
    "create_rule_engine_adapter",
    "create_validation_worker_adapter",
    "filter_candidate",
    "score_candidate",
]
