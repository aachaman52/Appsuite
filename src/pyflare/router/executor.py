"""Execution and resilient fallback engine for PyFlare Router."""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from pyflare.router.adapters import AdapterUnavailableError, ExecutionTimeoutError, create_rule_engine_adapter
from pyflare.router.history import RouterHistoryTracker
from pyflare.router.models import (
    HardwareTier,
    RouteCandidate,
    RouteDecision,
    RouteOutcome,
    TaskSpec,
)


class CandidateExecutionAttempt(BaseModel):
    candidate_id: str
    attempt_number: int
    success: bool
    duration_seconds: float
    error: Optional[str] = None
    is_retryable: bool = True


class RouteExecutionResult(BaseModel):
    task_id: str
    success: bool
    final_candidate_id: Optional[str] = None
    output: Any = None
    total_duration_seconds: float = 0.0
    total_cost_usd: float = 0.0
    attempts: List[CandidateExecutionAttempt] = Field(default_factory=list)
    error_summary: Optional[str] = None


class RouterExecutor:
    """
    Executes a RouteDecision, orchestrating primary execution and ordered fallbacks
    with loop prevention, non-retryable failure detection, real hardware tier tracking,
    timeout enforcement, and history recording.
    """

    def __init__(
        self,
        history_tracker: Optional[RouterHistoryTracker] = None,
        max_retries_per_candidate: int = 1,
        default_timeout_seconds: float = 30.0,
        adapters: Optional[Dict[str, Callable[[TaskSpec, RouteCandidate], Any]]] = None,
    ) -> None:
        self.history_tracker = history_tracker or RouterHistoryTracker()
        self.max_retries_per_candidate = max_retries_per_candidate
        self.default_timeout_seconds = default_timeout_seconds
        self.adapters: Dict[str, Callable[[TaskSpec, RouteCandidate], Any]] = adapters or {}

        # Register default built-in deterministic rule engine adapter if not provided
        if "local-fallback-rules" not in self.adapters:
            self.adapters["local-fallback-rules"] = create_rule_engine_adapter()
        if "local_rules" not in self.adapters:
            self.adapters["local_rules"] = create_rule_engine_adapter()

    def register_adapter(self, key: str, handler: Callable[[TaskSpec, RouteCandidate], Any]) -> None:
        """Register a custom execution callable for a specific candidate ID or provider type."""
        self.adapters[key] = handler

    def execute(self, task: TaskSpec, decision: RouteDecision) -> RouteExecutionResult:
        """
        Execute the primary route and fallbacks if necessary.
        """
        start_time = time.time()
        attempts: List[CandidateExecutionAttempt] = []
        attempted_candidates: Set[str] = set()

        # Extract actual hardware tier from route decision
        hw_tier_val = decision.hardware_profile_summary.get("hardware_tier", HardwareTier.MID)
        if isinstance(hw_tier_val, str):
            try:
                actual_hw_tier = HardwareTier(hw_tier_val)
            except ValueError:
                actual_hw_tier = HardwareTier.MID
        elif isinstance(hw_tier_val, HardwareTier):
            actual_hw_tier = hw_tier_val
        else:
            actual_hw_tier = HardwareTier.MID

        if not decision.selected_candidate:
            return RouteExecutionResult(
                task_id=task.task_id,
                success=False,
                error_summary="No eligible candidate route available in decision plan.",
                total_duration_seconds=time.time() - start_time,
            )

        # Build ordered sequence of candidates to try
        candidates_to_try: List[RouteCandidate] = [decision.selected_candidate] + decision.fallback_candidates
        total_cost = 0.0

        for candidate in candidates_to_try:
            cid = candidate.candidate_id
            if cid in attempted_candidates:
                continue  # Loop prevention
            attempted_candidates.add(cid)

            # Never execute unavailable candidates
            if not candidate.is_available:
                reason = candidate.unavailability_reason or "Candidate is marked unavailable"
                attempts.append(CandidateExecutionAttempt(
                    candidate_id=cid,
                    attempt_number=1,
                    success=False,
                    duration_seconds=0.0,
                    error=f"Candidate unavailable: {reason}",
                    is_retryable=False,
                ))
                continue

            # Try candidate with retries
            for attempt_idx in range(1, self.max_retries_per_candidate + 2):
                t0 = time.time()
                try:
                    output = self._run_candidate_with_timeout(task, candidate)
                    dur = time.time() - t0
                    total_cost += candidate.estimated_cost_usd

                    attempts.append(CandidateExecutionAttempt(
                        candidate_id=cid,
                        attempt_number=attempt_idx,
                        success=True,
                        duration_seconds=dur,
                    ))

                    # Record success in history with actual HardwareTier
                    self.history_tracker.record_outcome(RouteOutcome(
                        task_id=task.task_id,
                        candidate_id=cid,
                        task_type=task.task_type,
                        success=True,
                        duration_seconds=dur,
                        cost_usd=candidate.estimated_cost_usd,
                        retry_count=attempt_idx - 1,
                        validation_score=1.0,
                        hardware_tier=actual_hw_tier,
                        timestamp=time.time(),
                    ))

                    return RouteExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        final_candidate_id=cid,
                        output=output,
                        total_duration_seconds=time.time() - start_time,
                        total_cost_usd=total_cost,
                        attempts=attempts,
                    )

                except Exception as exc:
                    dur = time.time() - t0
                    err_msg = str(exc)
                    is_retryable = self._is_retryable_error(exc)

                    attempts.append(CandidateExecutionAttempt(
                        candidate_id=cid,
                        attempt_number=attempt_idx,
                        success=False,
                        duration_seconds=dur,
                        error=err_msg,
                        is_retryable=is_retryable,
                    ))

                    # Record failure in history with actual HardwareTier
                    self.history_tracker.record_outcome(RouteOutcome(
                        task_id=task.task_id,
                        candidate_id=cid,
                        task_type=task.task_type,
                        success=False,
                        duration_seconds=dur,
                        cost_usd=0.0,
                        error_message=err_msg,
                        retry_count=attempt_idx - 1,
                        validation_score=0.0,
                        hardware_tier=actual_hw_tier,
                        timestamp=time.time(),
                    ))

                    if not is_retryable:
                        # Skip directly to next fallback candidate
                        break

        # If all candidates and fallbacks were exhausted
        return RouteExecutionResult(
            task_id=task.task_id,
            success=False,
            total_duration_seconds=time.time() - start_time,
            total_cost_usd=total_cost,
            attempts=attempts,
            error_summary=f"All candidate routes exhausted ({len(attempts)} total attempts across {len(attempted_candidates)} candidates).",
        )

    def _run_candidate_with_timeout(self, task: TaskSpec, candidate: RouteCandidate) -> Any:
        """Run candidate enforcing timeout constraint."""
        timeout = task.preferred_latency_seconds or self.default_timeout_seconds

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_candidate, task, candidate)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise ExecutionTimeoutError(
                    f"Candidate '{candidate.candidate_id}' execution timed out after {timeout:.1f}s"
                )

    def _run_candidate(self, task: TaskSpec, candidate: RouteCandidate) -> Any:
        """Dispatch task to registered adapter; raise AdapterUnavailableError if missing."""
        # 1. Direct candidate adapter
        if candidate.candidate_id in self.adapters:
            return self.adapters[candidate.candidate_id](task, candidate)

        # 2. Provider type adapter
        if candidate.provider_type in self.adapters:
            return self.adapters[candidate.provider_type](task, candidate)

        # 3. No adapter exists -> Raise typed error (NO fake default success)
        raise AdapterUnavailableError(
            f"No execution adapter available for candidate '{candidate.candidate_id}' (provider_type='{candidate.provider_type}')"
        )

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Determine if an exception is transient (retryable) vs permanent."""
        if isinstance(exc, AdapterUnavailableError):
            return False

        msg = str(exc).lower()
        non_retryable_keywords = [
            "authentication",
            "unauthorized",
            "401",
            "forbidden",
            "403",
            "invalid api key",
            "invalid input",
            "policy violation",
            "permission denied",
            "validation error",
            "valueerror",
            "adapterunavailableerror",
        ]
        for kw in non_retryable_keywords:
            if kw in msg:
                return False
        return True
