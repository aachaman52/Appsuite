from __future__ import annotations

import unittest

from pyflare_control.models import (
    ExecutionKind,
    HardwareSnapshot,
    Permission,
    Provider,
    ProviderMetrics,
    ResourceBudget,
    TaskSpec,
)
from pyflare_control.scheduler import (
    AdmissionStatus,
    JobPriority,
    Reservation,
    ResourceScheduler,
)


class SchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = TaskSpec(
            task_id="task",
            project_id="project",
            domain="game_development",
            operation="implement",
            required_capabilities=frozenset({"unity.modify"}),
            permissions=frozenset({Permission.READ, Permission.WRITE}),
            resource_budget=ResourceBudget(4000, 2000, 40, 0),
        )
        self.provider = Provider(
            provider_id="unity-worker",
            kind=ExecutionKind.APPLICATION,
            capabilities=frozenset({"unity.modify"}),
            metrics=ProviderMetrics(0.9, 0.9, 0.8, sample_count=20),
            ram_mb=1000,
            vram_mb=500,
        )
        self.hardware = HardwareSnapshot(
            captured_at="now",
            cpu_threads=8,
            cpu_available_percent=80,
            ram_available_mb=5000,
            vram_available_mb=3000,
            disk_available_mb=10000,
            online=False,
            installed_applications=frozenset({"unity"}),
        )

    def test_admits_with_headroom(self) -> None:
        decision = ResourceScheduler().admit(
            self.task,
            self.provider,
            self.hardware,
        )
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)

    def test_preempts_only_lower_priority_preemptible_work(self) -> None:
        reservations = (
            Reservation(
                "background-model",
                ram_mb=3500,
                vram_mb=1500,
                cpu_percent=30,
                priority=JobPriority.BACKGROUND_NORMAL,
                preemptible=True,
            ),
        )
        decision = ResourceScheduler().admit(
            self.task,
            self.provider,
            self.hardware,
            reservations,
            priority=JobPriority.INTERACTIVE_CRITICAL,
        )
        self.assertEqual(decision.status, AdmissionStatus.ADMITTED)
        self.assertEqual(decision.preempt_reservation_ids, ("background-model",))


if __name__ == "__main__":
    unittest.main()
