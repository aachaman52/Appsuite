"""Versioned domain contracts shared by the PyFlare control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ExecutionKind(StrEnum):
    DETERMINISTIC = "deterministic"
    APPLICATION = "application"
    LOCAL_MODEL = "local_model"
    CLOUD_MODEL = "cloud_model"
    REMOTE_WORKSTATION = "remote_workstation"


class PrivacyClass(StrEnum):
    LOCAL_ONLY = "local_only"
    LOCAL_PREFERRED = "local_preferred"
    CLOUD_ALLOWED = "cloud_allowed"


class LatencyClass(StrEnum):
    INTERACTIVE = "interactive"
    FOREGROUND = "foreground"
    BATCH = "batch"


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    INSTALL = "install"
    SYSTEM_CHANGE = "system_change"


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_ram_mb: int
    max_vram_mb: int = 0
    max_cpu_percent: int = 100
    max_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.max_ram_mb < 0 or self.max_vram_mb < 0:
            raise ValueError("memory budgets cannot be negative")
        if not 1 <= self.max_cpu_percent <= 100:
            raise ValueError("max_cpu_percent must be in [1, 100]")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd cannot be negative")


@dataclass(frozen=True, slots=True)
class TaskSpec:
    task_id: str
    project_id: str
    domain: str
    operation: str
    required_capabilities: frozenset[str]
    permissions: frozenset[Permission]
    resource_budget: ResourceBudget
    privacy: PrivacyClass = PrivacyClass.LOCAL_PREFERRED
    latency: LatencyClass = LatencyClass.FOREGROUND
    allow_cloud: bool = False
    allow_remote_compute: bool = False
    requires_validation: bool = True
    expected_input_tokens: int = 0
    expected_output_tokens: int = 0
    required_applications: frozenset[str] = field(default_factory=frozenset)
    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not self.task_id or not self.project_id:
            raise ValueError("task_id and project_id are required")
        if not self.domain or not self.operation:
            raise ValueError("domain and operation are required")
        if not self.required_capabilities:
            raise ValueError("at least one required capability is required")
        if self.expected_input_tokens < 0 or self.expected_output_tokens < 0:
            raise ValueError("token estimates cannot be negative")
        if self.privacy is PrivacyClass.LOCAL_ONLY and self.allow_cloud:
            raise ValueError("local_only tasks cannot allow cloud execution")


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    version: str
    required_permissions: frozenset[Permission]
    offline: bool
    side_effecting: bool
    validation_capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ProviderMetrics:
    quality: float
    historical_success: float
    latency_fitness: float
    availability: float = 1.0
    sample_count: int = 0

    def __post_init__(self) -> None:
        for name in ("quality", "historical_success", "latency_fitness", "availability"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")


@dataclass(frozen=True, slots=True)
class Provider:
    provider_id: str
    kind: ExecutionKind
    capabilities: frozenset[str]
    metrics: ProviderMetrics
    ram_mb: int = 0
    vram_mb: int = 0
    estimated_cost_usd: float = 0.0
    requires_network: bool = False
    required_applications: frozenset[str] = field(default_factory=frozenset)
    available: bool = True
    circuit_open: bool = False

    def __post_init__(self) -> None:
        if self.ram_mb < 0 or self.vram_mb < 0 or self.estimated_cost_usd < 0:
            raise ValueError("provider resources and cost cannot be negative")


@dataclass(frozen=True, slots=True)
class HardwareSnapshot:
    captured_at: str
    cpu_threads: int
    cpu_available_percent: float
    ram_available_mb: int
    vram_available_mb: int | None
    disk_available_mb: int
    online: bool
    installed_applications: frozenset[str]
    thermal_state: str = "unknown"
    foreground_application: str | None = None

    def __post_init__(self) -> None:
        if self.cpu_threads < 1:
            raise ValueError("cpu_threads must be positive")
        if not 0 <= self.cpu_available_percent <= 100:
            raise ValueError("cpu_available_percent must be in [0, 100]")
        if min(self.ram_available_mb, self.disk_available_mb) < 0:
            raise ValueError("available resources cannot be negative")
        if self.vram_available_mb is not None and self.vram_available_mb < 0:
            raise ValueError("vram_available_mb cannot be negative")
