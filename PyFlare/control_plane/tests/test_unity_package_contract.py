import json
import unittest
from pathlib import Path


PACKAGE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "integrations"
    / "unity"
    / "com.aachmanstudios.pyflare.automation"
)


class UnityPackageContractTests(unittest.TestCase):
    def test_manifest_is_a_valid_editor_package(self) -> None:
        manifest = json.loads(
            (PACKAGE_ROOT / "package.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            manifest["name"],
            "com.aachmanstudios.pyflare.automation",
        )
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertGreaterEqual(int(manifest["unity"].split(".")[0]), 6000)

    def test_bridge_keeps_foundation_security_boundaries(self) -> None:
        source = (PACKAGE_ROOT / "Editor" / "PyFlareUnityBridge.cs").read_text(
            encoding="utf-8"
        )
        security = (PACKAGE_ROOT / "Editor" / "BridgeSecurity.cs").read_text(
            encoding="utf-8"
        )

        self.assertIn('http://127.0.0.1:47831/', source)
        self.assertNotIn("0.0.0.0", source)
        self.assertIn("X-PyFlare-Token", source)
        self.assertIn("PYFLARE_UNITY_BRIDGE_TOKEN", source)
        self.assertIn("MaximumRequestBytes", security)
        self.assertIn("IPAddress.IsLoopback", security)
        self.assertIn("Undo.RegisterCreatedObjectUndo", source)
        self.assertIn("save_scene_not_supported_in_bridge_v0_1", source)

    def test_idempotency_store_does_not_reference_bridge_secret(self) -> None:
        source = (
            PACKAGE_ROOT / "Editor" / "BridgeIdempotencyStore.cs"
        ).read_text(encoding="utf-8")

        self.assertNotIn("PYFLARE_UNITY_BRIDGE_TOKEN", source)
        self.assertIn("request_fingerprint", source)
        self.assertIn('"Library"', source)


if __name__ == "__main__":
    unittest.main()
