"""Acceptance tests for PyFlare First-Boot Onboarding and Failure Recovery (Item 2)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Add filesystem pyflare-firstrun path
ROOT = Path(__file__).resolve().parents[2]
FIRSTBOOT_SCRIPT = ROOT / "filesystem" / "opt" / "pyflare" / "bin" / "pyflare-firstrun"

sys.path.insert(0, str(FIRSTBOOT_SCRIPT.parent))
# Import the module
import importlib.util
from importlib.machinery import SourceFileLoader

loader = SourceFileLoader("pyflare_firstrun", str(FIRSTBOOT_SCRIPT))
spec = importlib.util.spec_from_loader("pyflare_firstrun", loader)
firstrun_mod = importlib.util.module_from_spec(spec)
loader.exec_module(firstrun_mod)


class FirstBootAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_first_boot_flow(self) -> None:
        """First boot detects hardware, selects model, creates user identity, and writes state."""
        state = firstrun_mod.execute_first_boot(
            data_dir=self.data_dir,
            username="gamedev",
            password="SecurePass2027!",
        )

        self.assertEqual(state["status"], "completed")
        self.assertIn("cpu_threads", state["hardware"])
        self.assertIn(state["model_selection"]["tier"], ["small", "medium", "large", "api_only"])
        self.assertEqual(state["user_created"], "gamedev")

        state_file = self.data_dir / "firstboot_state.json"
        self.assertTrue(state_file.exists())
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(loaded["status"], "completed")

    def test_first_boot_api_only_choice(self) -> None:
        """User can choose API-only mode during first boot."""
        state = firstrun_mod.execute_first_boot(
            data_dir=self.data_dir,
            force_api_only=True,
        )
        self.assertEqual(state["model_selection"]["tier"], "api_only")
        self.assertIsNone(state["model_selection"]["recommended_model"])

    def test_first_boot_with_provider_credentials(self) -> None:
        """First boot securely configures third-party provider credentials."""
        state = firstrun_mod.execute_first_boot(
            data_dir=self.data_dir,
            provider_id="anthropic",
            api_key="sk-ant-test-key-12345",
        )
        self.assertIn("anthropic", state["configured_providers"])

        # Check auth db
        auth_mgr = firstrun_mod.AuthManager(self.data_dir / "auth.sqlite3")
        cred = auth_mgr.get_provider_credential("anthropic")
        self.assertEqual(cred, "sk-ant-test-key-12345")

    def test_first_boot_idempotency_and_recovery(self) -> None:
        """Subsequent or retried first-boot calls handle existing state gracefully."""
        # First call
        firstrun_mod.execute_first_boot(
            data_dir=self.data_dir,
            username="repeat_user",
            password="SecurePass123!",
        )
        # Second call (retry/recovery)
        state2 = firstrun_mod.execute_first_boot(
            data_dir=self.data_dir,
            username="repeat_user",
            password="SecurePass123!",
        )
        self.assertEqual(state2["status"], "completed")


if __name__ == "__main__":
    unittest.main()
