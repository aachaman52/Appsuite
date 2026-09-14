"""Strict serialization for the PyFlare TaskSpec v1 contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from .models import (
    LatencyClass,
    Permission,
    PrivacyClass,
    ResourceBudget,
    TaskSpec,
)


class ContractValidationError(ValueError):
    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("invalid TaskSpec: " + "; ".join(self.issues))


class TaskSpecCodec:
    VERSION = "1.0"
    REQUIRED_FIELDS = frozenset(
        {
            "task_id",
            "project_id",
            "domain",
            "operation",
            "required_capabilities",
            "permissions",
            "resource_budget",
        }
    )
    OPTIONAL_FIELDS = frozenset(
        {
            "schema_version",
            "privacy",
            "latency",
            "allow_cloud",
            "allow_remote_compute",
            "requires_validation",
            "expected_input_tokens",
            "expected_output_tokens",
            "required_applications",
            "metadata",
        }
    )

    @classmethod
    def load(cls, raw: Mapping[str, Any]) -> TaskSpec:
        if not isinstance(raw, Mapping):
            raise ContractValidationError(("document must be an object",))

        issues: list[str] = []
        keys = frozenset(raw)
        missing = cls.REQUIRED_FIELDS - keys
        unknown = keys - cls.REQUIRED_FIELDS - cls.OPTIONAL_FIELDS
        if missing:
            issues.append("missing fields: " + ", ".join(sorted(missing)))
        if unknown:
            issues.append("unknown fields: " + ", ".join(sorted(unknown)))
        if raw.get("schema_version", cls.VERSION) != cls.VERSION:
            issues.append("schema_version must be 1.0")
        if issues:
            raise ContractValidationError(issues)

        task_id = cls._string(raw, "task_id", issues)
        project_id = cls._string(raw, "project_id", issues)
        domain = cls._string(raw, "domain", issues)
        operation = cls._string(raw, "operation", issues)
        capabilities = cls._string_set(raw, "required_capabilities", issues, required=True)
        applications = cls._string_set(raw, "required_applications", issues)
        permissions = cls._enum_set(raw, "permissions", Permission, issues)

        privacy = cls._enum_value(
            raw.get("privacy", PrivacyClass.LOCAL_PREFERRED.value),
            PrivacyClass,
            "privacy",
            issues,
        )
        latency = cls._enum_value(
            raw.get("latency", LatencyClass.FOREGROUND.value),
            LatencyClass,
            "latency",
            issues,
        )
        allow_cloud = cls._boolean(raw, "allow_cloud", issues, default=False)
        allow_remote = cls._boolean(raw, "allow_remote_compute", issues, default=False)
        requires_validation = cls._boolean(
            raw,
            "requires_validation",
            issues,
            default=True,
        )
        input_tokens = cls._integer(
            raw,
            "expected_input_tokens",
            issues,
            default=0,
            minimum=0,
        )
        output_tokens = cls._integer(
            raw,
            "expected_output_tokens",
            issues,
            default=0,
            minimum=0,
        )
        budget = cls._resource_budget(raw.get("resource_budget"), issues)

        metadata_raw = raw.get("metadata", {})
        if not isinstance(metadata_raw, Mapping):
            issues.append("metadata must be an object")
            metadata: Mapping[str, Any] = MappingProxyType({})
        else:
            metadata = MappingProxyType(dict(metadata_raw))

        if privacy is PrivacyClass.LOCAL_ONLY and allow_cloud:
            issues.append("local_only privacy cannot allow cloud execution")
        if issues:
            raise ContractValidationError(issues)

        return TaskSpec(
            task_id=task_id,
            project_id=project_id,
            domain=domain,
            operation=operation,
            required_capabilities=capabilities,
            permissions=permissions,
            resource_budget=budget,
            privacy=privacy,
            latency=latency,
            allow_cloud=allow_cloud,
            allow_remote_compute=allow_remote,
            requires_validation=requires_validation,
            expected_input_tokens=input_tokens,
            expected_output_tokens=output_tokens,
            required_applications=applications,
            metadata=metadata,
        )

    @classmethod
    def dump(cls, task: TaskSpec) -> dict[str, Any]:
        return {
            "schema_version": cls.VERSION,
            "task_id": task.task_id,
            "project_id": task.project_id,
            "domain": task.domain,
            "operation": task.operation,
            "required_capabilities": sorted(task.required_capabilities),
            "permissions": sorted(item.value for item in task.permissions),
            "resource_budget": {
                "max_ram_mb": task.resource_budget.max_ram_mb,
                "max_vram_mb": task.resource_budget.max_vram_mb,
                "max_cpu_percent": task.resource_budget.max_cpu_percent,
                "max_cost_usd": task.resource_budget.max_cost_usd,
            },
            "privacy": task.privacy.value,
            "latency": task.latency.value,
            "allow_cloud": task.allow_cloud,
            "allow_remote_compute": task.allow_remote_compute,
            "requires_validation": task.requires_validation,
            "expected_input_tokens": task.expected_input_tokens,
            "expected_output_tokens": task.expected_output_tokens,
            "required_applications": sorted(task.required_applications),
            "metadata": dict(task.metadata),
        }

    @staticmethod
    def _string(
        raw: Mapping[str, Any],
        field: str,
        issues: list[str],
    ) -> str:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{field} must be a non-empty string")
            return ""
        return value.strip()

    @staticmethod
    def _boolean(
        raw: Mapping[str, Any],
        field: str,
        issues: list[str],
        *,
        default: bool,
    ) -> bool:
        value = raw.get(field, default)
        if type(value) is not bool:
            issues.append(f"{field} must be a boolean")
            return default
        return value

    @staticmethod
    def _integer(
        raw: Mapping[str, Any],
        field: str,
        issues: list[str],
        *,
        default: int,
        minimum: int,
    ) -> int:
        value = raw.get(field, default)
        if type(value) is not int or value < minimum:
            issues.append(f"{field} must be an integer >= {minimum}")
            return default
        return value

    @staticmethod
    def _string_set(
        raw: Mapping[str, Any],
        field: str,
        issues: list[str],
        *,
        required: bool = False,
    ) -> frozenset[str]:
        value = raw.get(field, ())
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            issues.append(f"{field} must be an array of strings")
            return frozenset()
        values = list(value)
        if any(not isinstance(item, str) or not item.strip() for item in values):
            issues.append(f"{field} must contain only non-empty strings")
            return frozenset()
        normalized = [item.strip() for item in values]
        if len(normalized) != len(set(normalized)):
            issues.append(f"{field} must not contain duplicates")
        if required and not normalized:
            issues.append(f"{field} must contain at least one capability")
        return frozenset(normalized)

    @staticmethod
    def _enum_set(
        raw: Mapping[str, Any],
        field: str,
        enum_type: type[Permission],
        issues: list[str],
    ) -> frozenset[Permission]:
        values = TaskSpecCodec._string_set(raw, field, issues)
        output: set[Permission] = set()
        for value in values:
            try:
                output.add(enum_type(value))
            except ValueError:
                issues.append(f"invalid {field} value: {value}")
        return frozenset(output)

    @staticmethod
    def _enum_value(
        value: Any,
        enum_type: type[PrivacyClass | LatencyClass],
        field: str,
        issues: list[str],
    ) -> PrivacyClass | LatencyClass:
        try:
            return enum_type(value)
        except (TypeError, ValueError):
            issues.append(f"invalid {field} value: {value!r}")
            return next(iter(enum_type))

    @staticmethod
    def _resource_budget(
        raw: Any,
        issues: list[str],
    ) -> ResourceBudget:
        if not isinstance(raw, Mapping):
            issues.append("resource_budget must be an object")
            return ResourceBudget(0, 0, 100, 0)

        allowed = {
            "max_ram_mb",
            "max_vram_mb",
            "max_cpu_percent",
            "max_cost_usd",
        }
        required = {"max_ram_mb", "max_cpu_percent", "max_cost_usd"}
        unknown = set(raw) - allowed
        missing = required - set(raw)
        if unknown:
            issues.append("resource_budget has unknown fields: " + ", ".join(sorted(unknown)))
        if missing:
            issues.append("resource_budget missing fields: " + ", ".join(sorted(missing)))

        def integer(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
            value = raw.get(name, default)
            valid = type(value) is int and value >= minimum
            if maximum is not None:
                valid = valid and value <= maximum
            if not valid:
                suffix = f" and <= {maximum}" if maximum is not None else ""
                issues.append(f"resource_budget.{name} must be integer >= {minimum}{suffix}")
                return default
            return value

        ram = integer("max_ram_mb", 0, 0)
        vram = integer("max_vram_mb", 0, 0)
        cpu = integer("max_cpu_percent", 100, 1, 100)
        cost = raw.get("max_cost_usd", 0)
        if type(cost) not in {int, float} or cost < 0:
            issues.append("resource_budget.max_cost_usd must be a non-negative number")
            cost = 0
        return ResourceBudget(ram, vram, cpu, float(cost))
