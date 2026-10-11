from __future__ import annotations

import unittest

from pyflare_control.retry import (
    AttemptState,
    FailureKind,
    RetryAction,
    RetryBudget,
    RetryPolicy,
)
from pyflare_control.validation import (
    ValidationPolicy,
    ValidationResult,
    ValidationStatus,
)


class ValidationRetryTests(unittest.TestCase):
    def test_skipped_required_validator_is_not_pass(self) -> None:
        policy = ValidationPolicy(frozenset({"compile", "playmode"}))
        verdict = policy.evaluate(
            (
                ValidationResult("compile", "1", ValidationStatus.PASS),
                ValidationResult("playmode", "1", ValidationStatus.SKIPPED),
            )
        )
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.reason, "required_validator_inconclusive")

    def test_all_required_validators_must_pass(self) -> None:
        policy = ValidationPolicy(frozenset({"compile"}))
        verdict = policy.evaluate(
            (ValidationResult("compile", "1", ValidationStatus.PASS),)
        )
        self.assertTrue(verdict.accepted)

    def test_permission_failure_never_auto_retries(self) -> None:
        decision = RetryPolicy().decide(
            FailureKind.PERMISSION_DENIED,
            AttemptState(0, 0, 1, 0),
            RetryBudget(3, 2, 60, 1),
        )
        self.assertEqual(decision.action, RetryAction.ESCALATE_HUMAN)

    def test_repeated_identical_failure_opens_escalation(self) -> None:
        decision = RetryPolicy().decide(
            FailureKind.TRANSIENT_TRANSPORT,
            AttemptState(1, 0, 2, 0, repeated_failure_count=2),
            RetryBudget(5, 2, 60, 1),
        )
        self.assertEqual(decision.action, RetryAction.ESCALATE_HUMAN)


if __name__ == "__main__":
    unittest.main()
