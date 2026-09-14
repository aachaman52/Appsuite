"""Bounded deterministic retry and escalation policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureKind(StrEnum):
    TRANSIENT_TRANSPORT = "transient_transport"
    INVALID_STRUCTURED_OUTPUT = "invalid_structured_output"
    COMPILE_OR_TEST = "compile_or_test"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CAPABILITY_MISMATCH = "capability_mismatch"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_INCONCLUSIVE = "validation_inconclusive"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class RetryAction(StrEnum):
    RETRY_SAME_ROUTE = "retry_same_route"
    RETRY_WITH_CONTEXT = "retry_with_context"
    REROUTE = "reroute"
    RESCHEDULE = "reschedule"
    ESCALATE_HUMAN = "escalate_human"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class RetryBudget:
    max_attempts: int
    max_route_changes: int
    max_elapsed_seconds: int
    max_cost_usd: float

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_route_changes < 0:
            raise ValueError("invalid retry count budget")
        if self.max_elapsed_seconds < 1 or self.max_cost_usd < 0:
            raise ValueError("invalid retry time or cost budget")


@dataclass(frozen=True, slots=True)
class AttemptState:
    attempts: int
    route_changes: int
    elapsed_seconds: int
    cost_usd: float
    repeated_failure_count: int = 0


@dataclass(frozen=True, slots=True)
class RetryDecision:
    action: RetryAction
    reason: str


class RetryPolicy:
    def decide(
        self,
        failure: FailureKind,
        state: AttemptState,
        budget: RetryBudget,
    ) -> RetryDecision:
        if (
            state.attempts >= budget.max_attempts
            or state.elapsed_seconds >= budget.max_elapsed_seconds
            or state.cost_usd >= budget.max_cost_usd
        ):
            return RetryDecision(RetryAction.ESCALATE_HUMAN, "retry_budget_exhausted")
        if state.repeated_failure_count >= 2:
            return RetryDecision(RetryAction.ESCALATE_HUMAN, "repeated_identical_failure")
        if failure is FailureKind.PERMISSION_DENIED:
            return RetryDecision(RetryAction.ESCALATE_HUMAN, "permission_requires_approval")
        if failure is FailureKind.RESOURCE_EXHAUSTION:
            return RetryDecision(RetryAction.RESCHEDULE, "resources_temporarily_insufficient")
        if failure is FailureKind.TRANSIENT_TRANSPORT:
            return RetryDecision(RetryAction.RETRY_SAME_ROUTE, "transient_failure")
        if failure is FailureKind.INVALID_STRUCTURED_OUTPUT:
            if state.attempts == 0:
                return RetryDecision(RetryAction.RETRY_WITH_CONTEXT, "one_schema_repair_allowed")
            return self._reroute_or_escalate(state, budget)
        if failure is FailureKind.COMPILE_OR_TEST:
            return RetryDecision(RetryAction.RETRY_WITH_CONTEXT, "use_validation_diagnostics")
        if failure in {FailureKind.CAPABILITY_MISMATCH, FailureKind.UNSUPPORTED}:
            return self._reroute_or_escalate(state, budget)
        if failure is FailureKind.VALIDATION_INCONCLUSIVE:
            return RetryDecision(RetryAction.REROUTE, "select_stronger_validator")
        return RetryDecision(RetryAction.ESCALATE_HUMAN, "unclassified_failure")

    @staticmethod
    def _reroute_or_escalate(
        state: AttemptState,
        budget: RetryBudget,
    ) -> RetryDecision:
        if state.route_changes < budget.max_route_changes:
            return RetryDecision(RetryAction.REROUTE, "alternate_route_available")
        return RetryDecision(RetryAction.ESCALATE_HUMAN, "route_budget_exhausted")
