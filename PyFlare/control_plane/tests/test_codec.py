from __future__ import annotations

import unittest

from pyflare_control.codec import ContractValidationError, TaskSpecCodec
from pyflare_control.models import Permission, PrivacyClass


VALID_TASK = {
    "schema_version": "1.0",
    "task_id": "task-1",
    "project_id": "project-1",
    "domain": "game_development",
    "operation": "implement_feature",
    "required_capabilities": ["code.csharp.modify", "unity.scene.inspect"],
    "permissions": ["read", "write", "execute"],
    "resource_budget": {
        "max_ram_mb": 2048,
        "max_vram_mb": 512,
        "max_cpu_percent": 60,
        "max_cost_usd": 0.25,
    },
    "privacy": "local_preferred",
    "allow_cloud": True,
}


class TaskSpecCodecTests(unittest.TestCase):
    def test_round_trip_is_stable(self) -> None:
        loaded = TaskSpecCodec.load(VALID_TASK)
        self.assertEqual(loaded.privacy, PrivacyClass.LOCAL_PREFERRED)
        self.assertIn(Permission.WRITE, loaded.permissions)
        self.assertEqual(TaskSpecCodec.load(TaskSpecCodec.dump(loaded)), loaded)

    def test_unknown_fields_are_rejected(self) -> None:
        raw = dict(VALID_TASK)
        raw["unreviewed_power"] = "root"
        with self.assertRaises(ContractValidationError) as caught:
            TaskSpecCodec.load(raw)
        self.assertIn("unknown fields", str(caught.exception))

    def test_local_only_cannot_enable_cloud(self) -> None:
        raw = dict(VALID_TASK)
        raw["privacy"] = "local_only"
        raw["allow_cloud"] = True
        with self.assertRaises(ContractValidationError):
            TaskSpecCodec.load(raw)

    def test_boolean_is_not_accepted_as_integer(self) -> None:
        raw = dict(VALID_TASK)
        raw["expected_input_tokens"] = True
        with self.assertRaises(ContractValidationError):
            TaskSpecCodec.load(raw)


if __name__ == "__main__":
    unittest.main()
