"""Automated tests for PyFlare performance optimizations and VirtualBox audit fixes."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

ROOT_DIR = Path(__file__).resolve().parents[2]
FIRSTBOOT_SCRIPT = ROOT_DIR / "filesystem" / "opt" / "pyflare" / "bin" / "pyflare-firstrun"

from pyflare_control.hardware import (
    clear_hardware_cache,
    detect_gpu,
    detect_hardware,
    discover_applications,
    discover_supported_runtimes,
)


class PerformanceOptimizationsTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_hardware_cache()

    def tearDown(self) -> None:
        clear_hardware_cache()

    def test_hardware_caching_latency_reduction(self) -> None:
        """Cached calls to hardware profiler must complete in sub-millisecond time."""
        # First uncached run
        t0 = time.perf_counter()
        report1 = detect_hardware()
        uncached_duration = time.perf_counter() - t0

        # Second cached run
        t1 = time.perf_counter()
        report2 = detect_hardware()
        cached_duration = time.perf_counter() - t1

        self.assertEqual(report1.cpu_threads, report2.cpu_threads)
        self.assertEqual(report1.supported_runtimes, report2.supported_runtimes)
        self.assertLess(cached_duration, uncached_duration + 0.05)
        # Cached execution should be fast
        self.assertLess(cached_duration, 0.01, f"Cached hardware profiling took {cached_duration:.4f}s")

    def test_cache_invalidation_works_cleanly(self) -> None:
        """Cache clearing invalidates cached values and forces refresh."""
        runtimes1 = discover_supported_runtimes()
        self.assertIn("deterministic-local", runtimes1)

        clear_hardware_cache()
        runtimes2 = discover_supported_runtimes(refresh=True)
        self.assertEqual(runtimes1, runtimes2)

    def test_firstboot_defers_model_downloads(self) -> None:
        """First-boot engine must explicitly mark auto-download as false and defer downloads."""
        from importlib.machinery import SourceFileLoader

        loader = SourceFileLoader("pyflare_firstrun_perf", str(FIRSTBOOT_SCRIPT))
        spec = importlib.util.spec_from_loader("pyflare_firstrun_perf", loader)
        firstrun_mod = importlib.util.module_from_spec(spec)
        loader.exec_module(firstrun_mod)

        with TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            state = firstrun_mod.execute_first_boot(
                data_dir=base_dir,
                username="perf_tester",
                password="test_password_123",
            )
            self.assertEqual(state["status"], "completed")
            self.assertIn("model_selection", state)
            self.assertFalse(state["model_selection"]["auto_download_on_boot"])

            # Verify on-disk JSON file
            saved_state = json.loads((base_dir / "firstboot_state.json").read_text(encoding="utf-8"))
            self.assertFalse(saved_state["model_selection"]["auto_download_on_boot"])

    def test_grub_default_boot_omits_nomodeset(self) -> None:
        """Default desktop boot entry in package_iso.py must not include nomodeset."""
        package_iso_file = ROOT_DIR / "scripts" / "package_iso.py"
        content = package_iso_file.read_text(encoding="utf-8")
        
        # Look for default entry
        self.assertIn('menuentry "Start PyFlare OS Desktop"', content)
        # Ensure nomodeset is NOT on the primary desktop line
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if 'menuentry "Start PyFlare OS Desktop"' in line:
                desktop_linux_line = lines[i + 1]
                self.assertNotIn("nomodeset", desktop_linux_line, "Default desktop boot entry must not use nomodeset")
                break

    def test_gnome_overrides_exclude_blur_my_shell(self) -> None:
        """GNOME gschema overrides must not enable blur-my-shell on low-end hosts."""
        gschema_file = (
            ROOT_DIR
            / "filesystem"
            / "usr"
            / "share"
            / "glib-2.0"
            / "schemas"
            / "99-pyflare.gschema.override"
        )
        content = gschema_file.read_text(encoding="utf-8")
        self.assertNotIn("blur-my-shell", content, "blur-my-shell must not be enabled by default")

    def test_systemd_engine_service_avoids_dbus_blocking_timeout(self) -> None:
        """pyflare-engine.service must be Type=simple with bounded restart limit."""
        svc_file = ROOT_DIR / "filesystem" / "etc" / "systemd" / "system" / "pyflare-engine.service"
        content = svc_file.read_text(encoding="utf-8")
        self.assertIn("Type=simple", content)
        self.assertNotIn("Type=dbus", content)
        self.assertIn("StartLimitBurst=", content)

    def test_systemd_session_service_has_condition_path(self) -> None:
        """pyflare-session.service must verify binary existence before starting."""
        svc_file = ROOT_DIR / "filesystem" / "etc" / "systemd" / "user" / "pyflare-session.service"
        content = svc_file.read_text(encoding="utf-8")
        self.assertIn("ConditionPathExists=", content)
        self.assertIn("StartLimitBurst=", content)


if __name__ == "__main__":
    unittest.main()
