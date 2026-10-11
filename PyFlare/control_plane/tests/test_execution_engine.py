"""Acceptance tests for End-to-End Execution Pipeline (Section 6)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pyflare_control.audit import AuditLog
from pyflare_control.context import ProjectContextManager
from pyflare_control.execution_engine import (
    ExecutionEngine,
    ExecutionRequest,
)
from pyflare_control.hardware import HardwareSnapshot
from pyflare_control.journal import TaskJournal
from pyflare_control.models import (
    Capability,
    ExecutionKind,
    Permission,
    PrivacyClass,
    Provider,
    ProviderMetrics,
    ResourceBudget,
    TaskSpec,
)
from pyflare_control.registry import CapabilityRegistry, ProviderRegistry
from pyflare_control.router import DeterministicRouter
from pyflare_control.scheduler import ResourceScheduler
from pyflare_control.security import PermissionGrant
from pyflare_control.unity_client import (
    UnityBridgeClient,
    UnityBridgeConfig,
    UnityBridgeTransportError,
)
from pyflare_control.unity_protocol import (
    OperationStatus,
    UnityCommand,
    UnityResponse,
)


def sample_hardware() -> HardwareSnapshot:
    return HardwareSnapshot(
        captured_at="2026-10-11T00:00:00Z",
        cpu_threads=8,
        cpu_available_percent=85.0,
        ram_available_mb=12000,
        vram_available_mb=6000,
        disk_available_mb=80000,
        online=True,
        installed_applications=frozenset({"unity", "git"}),
        foreground_application="unity",
    )


def sample_task(task_id: str = "task-unity-1", project_id: str = "proj-unity-1") -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        project_id=project_id,
        domain="game_development",
        operation="game_object.create",
        required_capabilities=frozenset({"unity.scene.modify"}),
        permissions=frozenset({Permission.READ, Permission.WRITE, Permission.EXECUTE}),
        resource_budget=ResourceBudget(
            max_ram_mb=4000,
            max_vram_mb=2000,
            max_cpu_percent=40,
            max_cost_usd=0.0,
        ),
        privacy=PrivacyClass.LOCAL_ONLY,
    )


class MockUnityBridgeClient(UnityBridgeClient):
    """Controllable test double for Unity Bridge HTTP communication."""

    def __init__(self, mode: str = "success") -> None:
        super().__init__(
            UnityBridgeConfig(
                endpoint="http://127.0.0.1:47831",
                token="test_mock_token_with_length_at_least_32_chars",
            )
        )
        self.mode = mode
        self.executed_commands: list[UnityCommand] = []

    def execute(self, command: UnityCommand) -> UnityResponse:
        self.executed_commands.append(command)
        if self.mode == "disconnected":
            raise UnityBridgeTransportError("Connection refused by Unity Editor at 127.0.0.1:47831")
        if self.mode == "rejected":
            return UnityResponse(
                protocol="pyflare-unity/1.0",
                request_id=command.request_id,
                status=OperationStatus.REJECTED,
                result=MappingProxyType({}),
                errors=("undo_registration_required",),
            )
        if self.mode == "validation_failed":
            return UnityResponse(
                protocol="pyflare-unity/1.0",
                request_id=command.request_id,
                status=OperationStatus.FAILED,
                result=MappingProxyType({}),
                errors=("compilation_failed",),
            )

        # Default success
        return UnityResponse(
            protocol="pyflare-unity/1.0",
            request_id=command.request_id,
            status=OperationStatus.SUCCEEDED,
            result=MappingProxyType(
                {
                    "object_id": "GlobalObjectId_i1_00000000000000000000000000000000",
                    "name": command.arguments.get("name", "NewGameObject"),
                    "scene_path": "Assets/Scenes/Main.unity",
                    "editor_state": {"mode": "edit", "compiling": False},
                }
            ),
            warnings=("scene_modified_but_not_saved",),
        )


class EndToEndExecutionEngineAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)

        # Context Manager
        self.context_mgr = ProjectContextManager(self.base_dir / "context.sqlite3")
        proj_dir = self.base_dir / "SampleProject"
        proj_dir.mkdir()
        (proj_dir / "Player.cs").write_text("class Player {}", encoding="utf-8")
        self.context_mgr.register_project("proj-unity-1", proj_dir)
        self.context_mgr.index_project("proj-unity-1")

        # Journal and Audit
        self.journal = TaskJournal(self.base_dir / "journal.sqlite3")
        self.audit_log = AuditLog(self.base_dir / "audit.jsonl")

        # Capabilities & Providers
        unity_cap = Capability(
            capability_id="unity.scene.modify",
            version="1.0",
            required_permissions=frozenset({Permission.READ, Permission.WRITE, Permission.EXECUTE}),
            offline=True,
            side_effecting=True,
        )
        unity_provider = Provider(
            provider_id="unity-editor-bridge",
            kind=ExecutionKind.APPLICATION,
            capabilities=frozenset({"unity.scene.modify"}),
            metrics=ProviderMetrics(quality=0.99, historical_success=0.98, latency_fitness=0.95),
            ram_mb=500,
            required_applications=frozenset({"unity"}),
        )

        capabilities = CapabilityRegistry([unity_cap])
        providers = ProviderRegistry([unity_provider])

        self.router = DeterministicRouter(capabilities, providers)
        self.scheduler = ResourceScheduler()
        self.mock_client = MockUnityBridgeClient(mode="success")

        self.engine = ExecutionEngine(
            context_manager=self.context_mgr,
            router=self.router,
            scheduler=self.scheduler,
            journal=self.journal,
            audit_log=self.audit_log,
            unity_client=self.mock_client,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _make_grant(
        self,
        task_id: str,
        caps: frozenset[str] = frozenset({"unity.scene.modify"}),
    ) -> PermissionGrant:
        return PermissionGrant(
            grant_id=f"grant_{task_id}",
            task_id=task_id,
            subject="user:aachman",
            permissions=frozenset({Permission.READ, Permission.WRITE, Permission.EXECUTE}),
            project_root=self.base_dir / "SampleProject",
            allowed_paths=("*",),
            allowed_capabilities=caps,
        )

    def test_acceptance_1_and_8_valid_task_completes_and_displays(self) -> None:
        """Acceptance Tests 1 & 8: Valid Unity task executes, passes validation, journals, and formats display."""
        task = sample_task("task-1", "proj-unity-1")
        grant = self._make_grant("task-1")
        req = ExecutionRequest(
            request_id="req-1",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Create a Player GameObject",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
            operation_arguments={"name": "Player"},
            register_undo=True,
        )

        res = self.engine.execute(req, sample_hardware())
        self.assertEqual(res.status, "succeeded")
        self.assertIsNotNone(res.unity_response)
        self.assertEqual(res.unity_response.status, OperationStatus.SUCCEEDED)
        self.assertIn("GlobalObjectId", res.unity_response.result["object_id"])

        # Acceptance 8: User display output verification
        self.assertIn("PyFlare Task Execution: task-1", res.display_output)
        self.assertIn("Route:       unity-editor-bridge", res.display_output)
        self.assertIn("Status:      SUCCEEDED", res.display_output)
        self.assertIn("Validation:  PASSED", res.display_output)
        self.assertIn("Object Name: Player", res.display_output)

    def test_acceptance_2_invalid_task_is_rejected(self) -> None:
        """Acceptance Test 2: Invalid task preconditions or parameters are rejected cleanly."""
        self.mock_client.mode = "rejected"
        task = sample_task("task-2", "proj-unity-1")
        grant = self._make_grant("task-2")
        req = ExecutionRequest(
            request_id="req-2",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Create GameObject without undo",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
            register_undo=False,  # Bridge requires undo
        )

        res = self.engine.execute(req, sample_hardware())
        self.assertEqual(res.status, "failed")
        self.assertIn("undo_registration_required", res.errors)

    def test_acceptance_3_disconnected_editor_actionable_error(self) -> None:
        """Acceptance Test 3: Disconnected Unity editor produces actionable error."""
        self.mock_client.mode = "disconnected"
        task = sample_task("task-3", "proj-unity-1")
        grant = self._make_grant("task-3")
        req = ExecutionRequest(
            request_id="req-3",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Create GameObject",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
        )

        res = self.engine.execute(req, sample_hardware())
        self.assertEqual(res.status, "failed")
        self.assertTrue(any("disconnected or unreachable" in err for err in res.errors))

    def test_acceptance_4_unauthorized_task_blocked(self) -> None:
        """Acceptance Test 4: Unauthorized tasks are blocked before execution."""
        task = sample_task("task-4", "proj-unity-1")
        # Grant missing unity.scene.modify capability
        empty_grant = self._make_grant("task-4", caps=frozenset({"code.read"}))
        req = ExecutionRequest(
            request_id="req-4",
            project_id="proj-unity-1",
            user_id="attacker",
            intent="Unauthorized Unity modification",
            task_spec=task,
            grant=empty_grant,
            operation="game_object.create",
        )

        res = self.engine.execute(req, sample_hardware())
        self.assertEqual(res.status, "rejected")
        self.assertEqual(len(self.mock_client.executed_commands), 0)  # Editor was never touched!
        self.assertTrue(any("Authorization denied" in err for err in res.errors))

    def test_acceptance_5_validation_detects_unsuccessful_operation(self) -> None:
        """Acceptance Test 5: Validation detects an unsuccessful operation."""
        self.mock_client.mode = "validation_failed"
        task = sample_task("task-5", "proj-unity-1")
        grant = self._make_grant("task-5")
        req = ExecutionRequest(
            request_id="req-5",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Failed operation",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
        )

        res = self.engine.execute(req, sample_hardware())
        self.assertEqual(res.status, "failed")
        self.assertTrue(any("Validation detected" in err for err in res.errors))

    def test_acceptance_6_audit_log_records_request_route_and_results(self) -> None:
        """Acceptance Test 6: Audit log records request, route, execution result, and validation result."""
        task = sample_task("task-6", "proj-unity-1")
        grant = self._make_grant("task-6")
        req = ExecutionRequest(
            request_id="req-6",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Create audited object",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
        )

        self.engine.execute(req, sample_hardware())
        events = self.audit_log.read_events()
        self.assertGreater(len(events), 0)
        event = next(e for e in events if e.payload.get("request_id") == "req-6")
        self.assertEqual(event.actor, "user:aachman")
        self.assertIn("unity-editor-bridge", event.payload.get("route", ""))
        self.assertEqual(event.task_id, "task-6")

    def test_acceptance_7_retrying_task_is_idempotent_no_duplicate(self) -> None:
        """Acceptance Test 7: Retrying a completed task replays cached result without duplicate execution."""
        task = sample_task("task-7", "proj-unity-1")
        grant = self._make_grant("task-7")
        req = ExecutionRequest(
            request_id="req-7",
            project_id="proj-unity-1",
            user_id="aachman",
            intent="Create idempotent object",
            task_spec=task,
            grant=grant,
            operation="game_object.create",
            idempotency_key="unique_idemp_key_12345",
        )

        # First execution dispatches to Unity bridge
        res1 = self.engine.execute(req, sample_hardware())
        self.assertEqual(res1.status, "succeeded")
        self.assertFalse(res1.is_cached_replay)
        self.assertEqual(len(self.mock_client.executed_commands), 1)

        # Second execution with same idempotency key replays cached result
        res2 = self.engine.execute(req, sample_hardware())
        self.assertEqual(res2.status, "succeeded")
        self.assertTrue(res2.is_cached_replay)
        self.assertEqual(len(self.mock_client.executed_commands), 1)  # NOT dispatched a second time!


if __name__ == "__main__":
    unittest.main()
