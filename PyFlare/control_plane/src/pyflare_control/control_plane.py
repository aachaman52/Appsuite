"""Composition root for route selection, authorization and admission."""

from __future__ import annotations

from dataclasses import dataclass

from .models import HardwareSnapshot, TaskSpec
from .router import DeterministicRouter, RouteDecision
from .scheduler import (
    AdmissionDecision,
    JobPriority,
    Reservation,
    ResourceScheduler,
)
from .security import Authorizer, PermissionGrant


@dataclass(frozen=True, slots=True)
class PlannedExecution:
    route: RouteDecision
    admission: AdmissionDecision


class ControlPlane:
    def __init__(
        self,
        *,
        router: DeterministicRouter,
        scheduler: ResourceScheduler,
    ) -> None:
        self.router = router
        self.scheduler = scheduler

    def plan(
        self,
        task: TaskSpec,
        hardware: HardwareSnapshot,
        grant: PermissionGrant,
        reservations: tuple[Reservation, ...] = (),
        *,
        priority: JobPriority = JobPriority.FOREGROUND_ASSIST,
    ) -> PlannedExecution:
        if grant.task_id != task.task_id:
            raise PermissionError("permission grant belongs to a different task")
        for capability_id in sorted(task.required_capabilities):
            Authorizer.require_capability(grant, capability_id)

        route = self.router.route(task, hardware)
        provider = self.router.providers.get(route.primary_provider_id)
        if provider is None:
            raise RuntimeError("route references an unknown provider")
        admission = self.scheduler.admit(
            task,
            provider,
            hardware,
            reservations,
            priority=priority,
        )
        return PlannedExecution(route=route, admission=admission)
