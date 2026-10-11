"""Tests for the PyFlare CLI."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pyflare_control.cli import main


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_cli(self, args: list[str]) -> tuple[int, dict | list]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(args)
        output = buf.getvalue()
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            parsed = {}
        return code, parsed

    def test_cli_hardware(self) -> None:
        code, data = self._run_cli(["hardware", "--vram-mb", "6144", "--foreground", "unity"])
        self.assertEqual(code, 0)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("vram_available_mb"), 6144)
        self.assertEqual(data.get("foreground_application"), "unity")

    def test_cli_models_list(self) -> None:
        code, data = self._run_cli(["models", "list"])
        self.assertEqual(code, 0)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        model_ids = [m["model_id"] for m in data]
        self.assertIn("pyflare-small-3b-q4", model_ids)

    def test_cli_models_recommend(self) -> None:
        code, data = self._run_cli(["models", "recommend", "--vram-mb", "8192"])
        self.assertEqual(code, 0)
        self.assertIsInstance(data, dict)
        self.assertIn("tier", data)
        self.assertTrue(data.get("is_compatible"))

    def test_cli_models_recommend_api_only(self) -> None:
        code, data = self._run_cli(["models", "recommend", "--api-only"])
        self.assertEqual(code, 0)
        self.assertEqual(data.get("tier"), "api_only")

    def test_cli_context_flow(self) -> None:
        proj_dir = self.base_dir / "TestProject"
        proj_dir.mkdir()
        (proj_dir / "Test.cs").write_text("class Test { void Run() {} }", encoding="utf-8")
        db_path = self.base_dir / "context.sqlite3"

        # Register
        code, reg_out = self._run_cli([
            "context", "register",
            "--project-id", "test-p1",
            "--path", str(proj_dir),
            "--db", str(db_path),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(reg_out.get("project_id"), "test-p1")

        # Index
        code, idx_out = self._run_cli([
            "context", "index",
            "--project-id", "test-p1",
            "--db", str(db_path),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(idx_out.get("status"), "ready")
        self.assertGreater(idx_out.get("total_chunks", 0), 0)

        # Query
        code, qry_out = self._run_cli([
            "context", "query",
            "--project-id", "test-p1",
            "--intent", "Run method",
            "--db", str(db_path),
        ])
        self.assertEqual(code, 0)
        self.assertGreater(len(qry_out.get("sources", [])), 0)

    def test_cli_auth_flow(self) -> None:
        db_path = self.base_dir / "auth.sqlite3"

        code, user_out = self._run_cli([
            "auth", "create-user",
            "--user-id", "dev1",
            "--password", "StrongPass123!",
            "--db", str(db_path),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(user_out.get("username"), "dev1")
        self.assertTrue(user_out.get("user_id", "").startswith("user_"))

        code, key_out = self._run_cli([
            "auth", "set-key",
            "--provider-id", "anthropic",
            "--api-key", "sk-ant-test-key",
            "--db", str(db_path),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(key_out.get("status"), "stored")


if __name__ == "__main__":
    unittest.main()
