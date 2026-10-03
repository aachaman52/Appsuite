"""Resource admission and priority policy for local PyFlare jobs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from .models import HardwareSnapshot, Provider, TaskSpec


class JobPriority(IntEnum):
    MAINTENANCE = 10
    BATCH_HEAVY = 20
    BACKGROUND_NORMAL = 30
    FOREGROUND_ASSIST = 40
    INTERACTIVE_CRITICAL = 50


class AdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    QUEUED = "queued"
    REROUTE_REQUIRED = "reroute_required"


@dataclass(frozen=True, slots=True)
class Reservation:
    reservation_id: str
    ram_mb: int
    vram_mb: int
    cpu_percent: int
    priority: JobPriority
    preemptible: bool = False


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    status: AdmissionStatus
    reason: str
    preempt_reservation_ids: tuple[str, ...] = ()


class ResourceScheduler:
    def __init__(
        self,
        *,
        ram_safety_margin_mb: int = 512,
        vram_safety_margin_mb: int = 256,
        cpu_safety_margin_percent: int = 15,
    ) -> None:
        self.ram_safety_margin_mb = ram_safety_margin_mb
        self.vram_safety_margin_mb = vram_safety_margin_mb
        self.cpu_safety_margin_percent = cpu_safety_margin_percent

    def admit(
        self,
        task: TaskSpec,
        provider: Provider,
        hardware: HardwareSnapshot,
        reservations: tuple[Reservation, ...] = (),
        *,
        priority: JobPriority = JobPriority.FOREGROUND_ASSIST,
    ) -> AdmissionDecision:
        if provider.ram_mb > task.resource_budget.max_ram_mb:
            return AdmissionDecision(AdmissionStatus.REROUTE_REQUIRED, "task_ram_budget")
        if provider.vram_mb > task.resource_budget.max_vram_mb:
            return AdmissionDecision(AdmissionStatus.REROUTE_REQUIRED, "task_vram_budget")

        reserved_ram = sum(item.ram_mb for item in reservations)
        reserved_vram = sum(item.vram_mb for item in reservations)
        reserved_cpu = sum(item.cpu_percent for item in reservations)

        ram_ok = (
            provider.ram_mb + reserved_ram + self.ram_safety_margin_mb
            <= hardware.ram_available_mb
        )
        vram_ok = provider.vram_mb == 0 or (
            hardware.vram_available_mb is not None
            and provider.vram_mb + reserved_vram + self.vram_safety_margin_mb
            <= hardware.vram_available_mb
        )
        cpu_ok = (
            reserved_cpu
            + min(task.resource_budget.max_cpu_percent, 100)
            + self.cpu_safety_margin_percent
            <= hardware.cpu_available_percent
        )

        if ram_ok and vram_ok and cpu_ok:
            return AdmissionDecision(AdmissionStatus.ADMITTED, "resources_available")

        preemptible = tuple(
            item
            for item in reservations
            if item.preemptible and item.priority < priority
        )
        if preemptible:
            freed_ram = sum(item.ram_mb for item in preemptible)
            freed_vram = sum(item.vram_mb for item in preemptible)
            freed_cpu = sum(item.cpu_percent for item in preemptible)
            ram_after = (
                provider.ram_mb
                + reserved_ram
                - freed_ram
                + self.ram_safety_margin_mb
                <= hardware.ram_available_mb
            )
            vram_after = provider.vram_mb == 0 or (
                hardware.vram_available_mb is not None
                and provider.vram_mb
                + reserved_vram
                - freed_vram
                + self.vram_safety_margin_mb
                <= hardware.vram_available_mb
            )
            cpu_after = (
                reserved_cpu
                - freed_cpu
                + min(task.resource_budget.max_cpu_percent, 100)
                + self.cpu_safety_margin_percent
                <= hardware.cpu_available_percent
            )
            if ram_after and vram_after and cpu_after:
                return AdmissionDecision(
                    AdmissionStatus.ADMITTED,
                    "preempt_lower_priority_work",
                    tuple(item.reservation_id for item in preemptible),
                )

        if provider.kind.value in {"local_model", "application"}:
            return AdmissionDecision(
                AdmissionStatus.REROUTE_REQUIRED,
                "local_resources_insufficient",
            )
        return AdmissionDecision(AdmissionStatus.QUEUED, "resources_temporarily_unavailable")
