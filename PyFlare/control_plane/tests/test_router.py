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

    def test_deterministic_reproducibility_same_inputs_same_route(self) -> None:
        """Section 5 Acceptance: Identical inputs produce identical routing decisions."""
        t = task()
        hw = hardware()
        first_decision = self.router.route(t, hw)

        for _ in range(50):
            repeated = self.router.route(t, hw)
            self.assertEqual(repeated.primary_provider_id, first_decision.primary_provider_id)
            self.assertEqual(repeated.fallback_provider_ids, first_decision.fallback_provider_ids)
            for e1, e2 in zip(first_decision.evaluations, repeated.evaluations, strict=True):
                self.assertEqual(e1.provider_id, e2.provider_id)
                self.assertEqual(e1.accepted, e2.accepted)
                self.assertEqual(e1.score, e2.score)
                self.assertEqual(e1.reasons, e2.reasons)

    def test_circuit_breaker_and_unavailable_provider_fallback(self) -> None:
        """Section 5 Acceptance: Unavailable providers trigger explicit fallback rules."""
        # Create a router where primary deterministic tool has open circuit
        broken_primary = Provider(
            provider_id="roslyn",
            kind=ExecutionKind.DETERMINISTIC,
            capabilities=frozenset({"code.rename"}),
            metrics=ProviderMetrics(quality=0.99, historical_success=0.1, latency_fitness=0.95),
            ram_mb=100,
            circuit_open=True,  # Tripped circuit breaker
        )
        working_fallback = provider("cloud-large", ExecutionKind.CLOUD_MODEL, quality=0.95, latency=0.7, cost=0.1, network=True)

        router = DeterministicRouter(
            self.router.capabilities,
            ProviderRegistry([broken_primary, working_fallback]),
        )
        decision = router.route(task(), hardware())
        self.assertEqual(decision.primary_provider_id, "cloud-large")
        roslyn_eval = next(e for e in decision.evaluations if e.provider_id == "roslyn")
        self.assertFalse(roslyn_eval.accepted)
        self.assertIn("provider_circuit_open", roslyn_eval.reasons)

    def test_unauthorized_task_never_routes(self) -> None:
        """Section 5 Acceptance: Unauthorized tasks are rejected before execution."""
        # Task lacks WRITE permission required by code.rename capability
        unauthorized_task = TaskSpec(
            task_id="unauth-1",
            project_id="p-1",
            domain="software",
            operation="rename",
            required_capabilities=frozenset({"code.rename"}),
            permissions=frozenset({Permission.READ}),  # Missing WRITE!
            resource_budget=ResourceBudget(1000, 0, 10, 0),
        )
        with self.assertRaises(ValueError) as ctx:
            self.router.route(unauthorized_task, hardware())
        self.assertIn("lacks permissions", str(ctx.exception))

    def test_insufficient_resources_produces_structured_explanation(self) -> None:
        """Section 5 Acceptance: Insufficient resources produce explainable structured evaluation."""
        # Task demands more RAM than available
        with self.assertRaises(NoRouteError) as ctx:
            self.router.route(task(), hardware(ram=50))  # Only 50 MB available
        evals = ctx.exception.evaluations
        for ev in evals:
            self.assertFalse(ev.accepted)
            self.assertTrue(any("ram" in r for r in ev.reasons))


if __name__ == "__main__":
    unittest.main()
