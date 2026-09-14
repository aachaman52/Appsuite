"""Deterministic capability router.

Models may provide measured metrics, but this module retains final authority.
Given the same TaskSpec, registries, hardware snapshot and policy, it returns
the same decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .models import (
    ExecutionKind,
    HardwareSnapshot,
    PrivacyClass,
    Provider,
    TaskSpec,
)
from .registry import CapabilityRegistry, ProviderRegistry


@dataclass(frozen=True, slots=True)
class RouterWeights:
    quality: float = 0.22
    historical_success: float = 0.24
    latency: float = 0.18
    resource_fitness: float = 0.14
    availability: float = 0.08
    cost_fitness: float = 0.06
    privacy_fitness: float = 0.04
    deterministic_preference: float = 0.12
    interference_penalty: float = 0.12


@dataclass(frozen=True, slots=True)
class RouterPolicy:
    policy_id: str = "default-v1"
    minimum_quality: float = 0.45
    minimum_historical_success: float = 0.20
    minimum_samples_for_history_gate: int = 10
    ram_safety_margin_mb: int = 512
    vram_safety_margin_mb: int = 256
    weights: RouterWeights = field(default_factory=RouterWeights)


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    provider_id: str
    accepted: bool
    score: float | None
    reasons: tuple[str, ...]
    components: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class RouteDecision:
    task_id: str
    policy_id: str
    primary_provider_id: str
    fallback_provider_ids: tuple[str, ...]
    evaluations: tuple[CandidateEvaluation, ...]


class NoRouteError(RuntimeError):
    def __init__(self, task_id: str, evaluations: tuple[CandidateEvaluation, ...]) -> None:
        super().__init__(f"no viable route for task {task_id}")
        self.task_id = task_id
        self.evaluations = evaluations


class DeterministicRouter:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        providers: ProviderRegistry,
        policy: RouterPolicy | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.providers = providers
        self.policy = policy or RouterPolicy()

    def route(self, task: TaskSpec, hardware: HardwareSnapshot) -> RouteDecision:
        self._validate_task_capabilities(task)
        evaluations = tuple(
            self._evaluate(provider, task, hardware)
            for provider in self.providers.all()
        )
        accepted = [item for item in evaluations if item.accepted]
        if not accepted:
            raise NoRouteError(task.task_id, evaluations)

        accepted.sort(
            key=lambda item: (-(item.score or 0.0), item.provider_id)
        )
        return RouteDecision(
            task_id=task.task_id,
            policy_id=self.policy.policy_id,
            primary_provider_id=accepted[0].provider_id,
            fallback_provider_ids=tuple(item.provider_id for item in accepted[1:]),
            evaluations=evaluations,
        )

    def _validate_task_capabilities(self, task: TaskSpec) -> None:
        unknown = task.required_capabilities - self.capabilities.ids()
        if unknown:
            raise ValueError(f"TaskSpec requires unknown capabilities: {sorted(unknown)}")
        missing_permissions: dict[str, list[str]] = {}
        for capability_id in task.required_capabilities:
            capability = self.capabilities.require(capability_id)
            missing = capability.required_permissions - task.permissions
            if missing:
                missing_permissions[capability_id] = sorted(str(item) for item in missing)
        if missing_permissions:
            raise ValueError(
                f"TaskSpec lacks permissions required by capabilities: {missing_permissions}"
            )

    def _evaluate(
        self,
        provider: Provider,
        task: TaskSpec,
        hardware: HardwareSnapshot,
    ) -> CandidateEvaluation:
        reasons: list[str] = []

        if not provider.available:
            reasons.append("provider_unavailable")
        if provider.circuit_open:
            reasons.append("provider_circuit_open")
        missing_capabilities = task.required_capabilities - provider.capabilities
        if missing_capabilities:
            reasons.append("missing_capabilities:" + ",".join(sorted(missing_capabilities)))
        if provider.requires_network and not hardware.online:
            reasons.append("network_unavailable")
        if provider.kind is ExecutionKind.CLOUD_MODEL and not task.allow_cloud:
            reasons.append("cloud_not_allowed")
        if provider.kind is ExecutionKind.REMOTE_WORKSTATION and not task.allow_remote_compute:
            reasons.append("remote_compute_not_allowed")
        if task.privacy is PrivacyClass.LOCAL_ONLY and (
            provider.requires_network
            or provider.kind in {ExecutionKind.CLOUD_MODEL, ExecutionKind.REMOTE_WORKSTATION}
        ):
            reasons.append("privacy_local_only")
        if provider.estimated_cost_usd > task.resource_budget.max_cost_usd:
            reasons.append("cost_budget_exceeded")
        if provider.ram_mb > task.resource_budget.max_ram_mb:
            reasons.append("task_ram_budget_exceeded")
        if provider.vram_mb > task.resource_budget.max_vram_mb:
            reasons.append("task_vram_budget_exceeded")
        if provider.ram_mb + self.policy.ram_safety_margin_mb > hardware.ram_available_mb:
            reasons.append("live_ram_insufficient")
        if (
            provider.vram_mb > 0
            and (
                hardware.vram_available_mb is None
                or provider.vram_mb + self.policy.vram_safety_margin_mb
                > hardware.vram_available_mb
            )
        ):
            reasons.append("live_vram_insufficient_or_unknown")
        required_apps = task.required_applications | provider.required_applications
        if not required_apps.issubset(hardware.installed_applications):
            reasons.append("required_application_missing")
        if provider.metrics.quality < self.policy.minimum_quality:
            reasons.append("quality_below_gate")
        if (
            provider.metrics.sample_count >= self.policy.minimum_samples_for_history_gate
            and provider.metrics.historical_success
            < self.policy.minimum_historical_success
        ):
            reasons.append("historical_success_below_gate")

        if reasons:
            return CandidateEvaluation(
                provider_id=provider.provider_id,
                accepted=False,
                score=None,
                reasons=tuple(reasons),
            )

        components = self._score_components(provider, task, hardware)
        score = round(sum(components.values()), 8)
        return CandidateEvaluation(
            provider_id=provider.provider_id,
            accepted=True,
            score=score,
            reasons=("accepted",),
            components=MappingProxyType(components),
        )

    def _score_components(
        self,
        provider: Provider,
        task: TaskSpec,
        hardware: HardwareSnapshot,
    ) -> dict[str, float]:
        weights = self.policy.weights
        ram_headroom = max(
            0.0,
            1.0 - provider.ram_mb / max(1, hardware.ram_available_mb),
        )
        if provider.vram_mb == 0:
            vram_headroom = 1.0
        else:
            vram_headroom = max(
                0.0,
                1.0 - provider.vram_mb / max(1, hardware.vram_available_mb or 1),
            )
        resource_fitness = (ram_headroom + vram_headroom) / 2.0

        if task.resource_budget.max_cost_usd == 0:
            cost_fitness = 1.0 if provider.estimated_cost_usd == 0 else 0.0
        else:
            cost_fitness = max(
                0.0,
                1.0 - provider.estimated_cost_usd / task.resource_budget.max_cost_usd,
            )

        privacy_fitness = 1.0
        if provider.kind in {ExecutionKind.CLOUD_MODEL, ExecutionKind.REMOTE_WORKSTATION}:
            privacy_fitness = 0.25 if task.privacy is PrivacyClass.LOCAL_PREFERRED else 0.75

        deterministic_bonus = (
            1.0
            if provider.kind in {ExecutionKind.DETERMINISTIC, ExecutionKind.APPLICATION}
            else 0.0
        )
        interference = 0.0
        if hardware.foreground_application in {"unity", "blender"}:
            interference = max(
                provider.ram_mb / max(1, hardware.ram_available_mb),
                provider.vram_mb / max(1, hardware.vram_available_mb or 1),
            )

        return {
            "quality": weights.quality * provider.metrics.quality,
            "historical_success": (
                weights.historical_success * provider.metrics.historical_success
            ),
            "latency": weights.latency * provider.metrics.latency_fitness,
            "resource_fitness": weights.resource_fitness * resource_fitness,
            "availability": weights.availability * provider.metrics.availability,
            "cost_fitness": weights.cost_fitness * cost_fitness,
            "privacy_fitness": weights.privacy_fitness * privacy_fitness,
            "deterministic_preference": (
                weights.deterministic_preference * deterministic_bonus
            ),
            "interference_penalty": -weights.interference_penalty * min(1.0, interference),
        }
