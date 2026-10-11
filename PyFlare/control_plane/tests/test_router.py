from __future__ import annotations

import unittest

from pyflare_control.models import (
    Capability,
    ExecutionKind,
    HardwareSnapshot,
    Permission,
    PrivacyClass,
    Provider,
    ProviderMetrics,
    ResourceBudget,
    TaskSpec,
)
from pyflare_control.registry import CapabilityRegistry, ProviderRegistry
from pyflare_control.router import DeterministicRouter, NoRouteError


def hardware(*, online: bool = True, ram: int = 8000) -> HardwareSnapshot:
    return HardwareSnapshot(
        captured_at="2026-09-14T00:00:00Z",
        cpu_threads=8,
        cpu_available_percent=90,
        ram_available_mb=ram,
        vram_available_mb=4000,
        disk_available_mb=100000,
        online=online,
        installed_applications=frozenset({"git"}),
    )


def task(*, allow_cloud: bool = True) -> TaskSpec:
    return TaskSpec(
        task_id="task-1",
        project_id="project-1",
        domain="software",
        operation="rename_symbol",
        required_capabilities=frozenset({"code.rename"}),
        permissions=frozenset({Permission.READ, Permission.WRITE}),
        resource_budget=ResourceBudget(
            max_ram_mb=6000,
            max_vram_mb=4000,
            max_cpu_percent=50,
            max_cost_usd=1.0,
        ),
        privacy=PrivacyClass.LOCAL_PREFERRED,
        allow_cloud=allow_cloud,
    )


def provider(
    provider_id: str,
    kind: ExecutionKind,
    *,
    quality: float,
    latency: float,
    cost: float = 0,
    network: bool = False,
    ram: int = 100,
) -> Provider:
    return Provider(
        provider_id=provider_id,
        kind=kind,
        capabilities=frozenset({"code.rename"}),
        metrics=ProviderMetrics(
            quality=quality,
            historical_success=0.9,
            latency_fitness=latency,
            sample_count=30,
        ),
        ram_mb=ram,
        estimated_cost_usd=cost,
        requires_network=network,
    )


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        capabilities = CapabilityRegistry(
            [
                Capability(
                    capability_id="code.rename",
                    version="1.0",
                    required_permissions=frozenset({Permission.READ, Permission.WRITE}),
                    offline=True,
                    side_effecting=True,
                )
            ]
        )
        providers = ProviderRegistry(
            [
                provider(
                    "roslyn",
                    ExecutionKind.DETERMINISTIC,
                    quality=0.92,
                    latency=0.98,
                ),
                provider(
                    "cloud-large",
                    ExecutionKind.CLOUD_MODEL,
                    quality=0.99,
                    latency=0.70,
                    cost=0.2,
                    network=True,
                    ram=0,
                ),
            ]
        )
        self.router = DeterministicRouter(capabilities, providers)

    def test_deterministic_tool_beats_unnecessary_cloud_model(self) -> None:
        decision = self.router.route(task(), hardware())
        self.assertEqual(decision.primary_provider_id, "roslyn")
        self.assertEqual(decision.fallback_provider_ids, ("cloud-large",))

    def test_cloud_is_hard_filtered_when_disallowed(self) -> None:
        decision = self.router.route(task(allow_cloud=False), hardware())
        self.assertEqual(decision.primary_provider_id, "roslyn")
        cloud = next(
            item for item in decision.evaluations if item.provider_id == "cloud-large"
        )
        self.assertIn("cloud_not_allowed", cloud.reasons)

    def test_offline_state_removes_cloud_route(self) -> None:
        decision = self.router.route(task(), hardware(online=False))
        self.assertEqual(decision.fallback_provider_ids, ())

    def test_no_route_contains_evaluations(self) -> None:
        with self.assertRaises(NoRouteError) as caught:
            self.router.route(task(), hardware(ram=100))
        self.assertTrue(caught.exception.evaluations)


if __name__ == "__main__":
    unittest.main()
