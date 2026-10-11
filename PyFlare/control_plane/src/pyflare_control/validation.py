"""Structured validator results and deterministic acceptance policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str
    message: str
    severity: FindingSeverity
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    validator_id: str
    validator_version: str
    status: ValidationStatus
    findings: tuple[ValidationFinding, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.validator_id or not self.validator_version:
            raise ValueError("validator identity and version are required")
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if self.status is ValidationStatus.PASS and any(
            finding.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL}
            for finding in self.findings
        ):
            raise ValueError("passing validation cannot contain error findings")


@dataclass(frozen=True, slots=True)
class ValidationVerdict:
    accepted: bool
    reason: str
    missing_validators: tuple[str, ...]
    failed_validators: tuple[str, ...]
    inconclusive_validators: tuple[str, ...]


class ValidationPolicy:
    def __init__(self, required_validators: frozenset[str]) -> None:
        self.required_validators = required_validators

    def evaluate(
        self,
        results: tuple[ValidationResult, ...],
    ) -> ValidationVerdict:
        by_id: dict[str, ValidationResult] = {}
        for result in results:
            if result.validator_id in by_id:
                raise ValueError(f"duplicate validator result: {result.validator_id}")
            by_id[result.validator_id] = result

        missing = tuple(sorted(self.required_validators - set(by_id)))
        failed = tuple(
            sorted(
                validator_id
                for validator_id, result in by_id.items()
                if validator_id in self.required_validators
                and result.status is ValidationStatus.FAIL
            )
        )
        inconclusive = tuple(
            sorted(
                validator_id
                for validator_id, result in by_id.items()
                if validator_id in self.required_validators
                and result.status
                in {ValidationStatus.INCONCLUSIVE, ValidationStatus.SKIPPED}
            )
        )
        if missing:
            return ValidationVerdict(False, "required_validator_missing", missing, failed, inconclusive)
        if failed:
            return ValidationVerdict(False, "required_validator_failed", missing, failed, inconclusive)
        if inconclusive:
            return ValidationVerdict(
                False,
                "required_validator_inconclusive",
                missing,
                failed,
                inconclusive,
            )
        return ValidationVerdict(True, "all_required_validators_passed", (), (), ())


EMPTY_VALIDATION_METADATA = MappingProxyType({})
