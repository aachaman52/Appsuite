"""Live Unity Editor End-to-End Integration Test (Section 6 / Item 3).

Executes a real vertical slice test against an actual Unity 6 Editor process:
- Creates / launches Unity Editor in batchmode with com.aachmanstudios.pyflare.automation
- Connects via loopback HTTP bridge
- Executes game_object.create through the ExecutionEngine
- Validates the real Unity response with assigned GlobalObjectId
- Verifies task transition to COMPLETED in the SQLite Journal
- Verifies audit record in the JSON Lines Audit Log
- Cleanly shuts down Unity Editor process
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pyflare_control.audit import AuditLog
from pyflare_control.context import ProjectContextManager
from pyflare_control.execution_engine import ExecutionEngine, ExecutionRequest
from pyflare_control.hardware import capture_snapshot
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
from pyflare_control.unity_client import UnityBridgeClient, UnityBridgeConfig
from pyflare_control.unity_protocol import OperationStatus

DEFAULT_UNITY_PATH = Path("C:/Program Files/Unity/Hub/Editor/6000.0.69f1/Editor/Unity.exe")
UNITY_FOUND = DEFAULT_UNITY_PATH.exists() or shutil.which("Unity") is not None or shutil.which("unity-editor") is not None


class LiveUnityIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(UNITY_FOUND, "Live Unity Editor 6 executable not installed on this host")
    def test_live_unity_end_to_end_vertical_slice(self) -> None:
        unity_exe = DEFAULT_UNITY_PATH if DEFAULT_UNITY_PATH.exists() else Path(shutil.which("Unity") or shutil.which("unity-editor"))
        repo_root = Path(__file__).resolve().parents[3]
        unity_pkg = repo_root / "PyFlare" / "integrations" / "unity" / "com.aachmanstudios.pyflare.automation"

        tmp_dir = TemporaryDirectory(ignore_cleanup_errors=True)
        base_dir = Path(tmp_dir.name)
        proj_dir = base_dir / "LiveProject"
        proj_dir.mkdir()

        # Setup minimal Unity package folders
        pkg_dst = proj_dir / "Packages" / "com.aachmanstudios.pyflare.automation"
        shutil.copytree(unity_pkg, pkg_dst)
        (proj_dir / "Assets").mkdir(exist_ok=True)
        (proj_dir / "ProjectSettings").mkdir(exist_ok=True)
        (proj_dir / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.69f1\n", encoding="utf-8")

        token = "test_live_secret_token_at_least_32_chars_12345"
        env = dict(os.environ)
        env["PYFLARE_UNITY_BRIDGE_ENABLED"] = "1"
        env["PYFLARE_UNITY_BRIDGE_TOKEN"] = token

        log_file = base_dir / "unity_batchmode.log"
        stop_file = proj_dir / "stop_unity_bridge.txt"

        # Launch Unity in batchmode
        proc = subprocess.Popen(
            [
                str(unity_exe),
                "-projectPath", str(proj_dir),
                "-batchmode",
                "-executeMethod", "AachmanStudios.PyFlare.Unity.PyFlareUnityBridge.RunBatchmodeBridge",
                "-logFile", str(log_file),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Poll /health endpoint until Unity bridge starts
            config = UnityBridgeConfig(endpoint="http://127.0.0.1:47831", token=token)
            client = UnityBridgeClient(config)

            connected = False
            deadline = time.time() + 120.0
            while time.time() < deadline:
                try:
                    resp = client.health()
                    if resp.get("status") in ("ready", "healthy"):
                        connected = True
                        break
                except Exception:
                    pass
                time.sleep(1.0)

            self.assertTrue(connected, f"Unity Bridge did not become healthy within 120s. Log: {log_file}")

            # Context Manager
            context_mgr = ProjectContextManager(base_dir / "context.sqlite3")
            context_mgr.register_project("proj-test-live", proj_dir)
            context_mgr.index_project("proj-test-live")

            # Journal and Audit
            journal = TaskJournal(base_dir / "journal.sqlite3")
            audit_log = AuditLog(base_dir / "audit.jsonl")

            # Providers & Router
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
            router = DeterministicRouter(
                CapabilityRegistry([unity_cap]),
                ProviderRegistry([unity_provider]),
            )
            scheduler = ResourceScheduler()

            engine = ExecutionEngine(
                context_manager=context_mgr,
                router=router,
                scheduler=scheduler,
                journal=journal,
                audit_log=audit_log,
                unity_client=client,
            )

            task_id = f"task-unity-{uuid.uuid4().hex[:8]}"
            task = TaskSpec(
                task_id=task_id,
                project_id="proj-test-live",
                domain="game_development",
                operation="game_object.create",
                required_capabilities=frozenset({"unity.scene.modify"}),
                permissions=frozenset({Permission.READ, Permission.WRITE, Permission.EXECUTE}),
                resource_budget=ResourceBudget(
                    max_ram_mb=2000,
                    max_vram_mb=1000,
                    max_cpu_percent=25,
                    max_cost_usd=0.0,
                ),
                privacy=PrivacyClass.LOCAL_ONLY,
            )
            grant = PermissionGrant(
                grant_id=f"grant_{task_id}",
                task_id=task_id,
                subject="user:aachman",
                permissions=frozenset({Permission.READ, Permission.WRITE, Permission.EXECUTE}),
                project_root=proj_dir,
                allowed_paths=("*",),
                allowed_capabilities=frozenset({"unity.scene.modify"}),
            )

            req = ExecutionRequest(
                request_id=f"req-{task_id}",
                project_id="proj-test-live",
                user_id="aachman",
                intent="Create Live GameObject",
                task_spec=task,
                grant=grant,
                operation="game_object.create",
                operation_arguments={"name": "PlayerUnit"},
                register_undo=True,
                save_scene=False,
            )

            hw = capture_snapshot(online=True, foreground_application="unity")
            hw = replace(hw, installed_applications=hw.installed_applications | frozenset({"unity"}))

            res = engine.execute(req, hw)

            # Assertions on vertical slice results
            self.assertEqual(res.status, "succeeded")
            self.assertIsNotNone(res.unity_response)
            self.assertEqual(res.unity_response.status, OperationStatus.SUCCEEDED)
            self.assertIn("GlobalObjectId", res.unity_response.result.get("object_id", ""))
            self.assertEqual(res.unity_response.result.get("name"), "PlayerUnit")

            # Assert Audit Log
            events = audit_log.read_events()
            self.assertTrue(any(e.task_id == task_id for e in events))

            # Assert Journal Task
            task_rec = journal.require_task(task_id)
            self.assertEqual(task_rec.status.value, "completed")

        finally:
            stop_file.write_text("stop", encoding="utf-8")
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            time.sleep(0.5)
            try:
                tmp_dir.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
