"""Acceptance tests for Hardware-Aware AI & Model Configuration (Section 7)."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyflare_control.hardware import HardwareReport, detect_hardware
from pyflare_control.model_registry import (
    InsufficientStorageError,
    ModelCapabilityRegistry,
    ModelMetadata,
    ModelTier,
)


class HardwareAndModelRegistryAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ModelCapabilityRegistry()

    def test_acceptance_1_hardware_detection_structured_report(self) -> None:
        """Acceptance Test 1: Hardware detection produces a structured report."""
        report = detect_hardware()
        self.assertIsInstance(report, HardwareReport)
        self.assertGreater(report.cpu_threads, 0)
        self.assertGreater(report.ram_total_mb, 0)
        self.assertGreater(report.ram_available_mb, 0)
        self.assertIsInstance(report.supported_runtimes, tuple)
        self.assertIn("deterministic-local", report.supported_runtimes)
        self.assertIsInstance(report.installed_applications, frozenset)

        # Convert to router snapshot
        snapshot = report.to_snapshot()
        self.assertEqual(snapshot.ram_available_mb, report.ram_available_mb)
        self.assertEqual(snapshot.cpu_threads, report.cpu_threads)

    def test_acceptance_2_missing_gpu_handled_safely(self) -> None:
        """Acceptance Test 2: Systems without GPUs are handled safely without crashing."""
        # Synthetic report with 0 GPU and no accelerator
        no_gpu_report = HardwareReport(
            cpu_architecture="x86_64",
            cpu_cores=4,
            cpu_threads=8,
            ram_total_mb=16384,
            ram_available_mb=10000,
            gpu_name=None,
            gpu_vram_mb=None,
            accelerator_type=None,
            storage_total_mb=500000,
            storage_available_mb=150000,
            supported_runtimes=("llama.cpp", "deterministic-local"),
            installed_applications=frozenset({"git"}),
            online=True,
            platform_system="Linux",
        )

        rec = self.registry.recommend(no_gpu_report)
        self.assertTrue(rec.is_compatible)
        # Medium fits in 10000 MB RAM and requires 0 VRAM
        self.assertEqual(rec.selected_tier, ModelTier.MEDIUM)
        self.assertIsNotNone(rec.recommended_model)
        self.assertEqual(rec.recommended_model.min_vram_mb, 0)

        # When RAM is sufficient (32 GB) but GPU is missing, Large tier fails specifically due to missing VRAM
        high_ram_no_gpu = HardwareReport(
            cpu_architecture="x86_64",
            cpu_cores=8,
            cpu_threads=16,
            ram_total_mb=65536,
            ram_available_mb=32000,
            gpu_name=None,
            gpu_vram_mb=None,
            accelerator_type=None,
            storage_total_mb=500000,
            storage_available_mb=150000,
            supported_runtimes=("llama.cpp", "deterministic-local"),
            installed_applications=frozenset({"git"}),
            online=True,
            platform_system="Linux",
        )
        ok, reason = self.registry.evaluate_model(self.registry.get("pyflare-large-14b-q4"), high_ram_no_gpu)
        self.assertFalse(ok)
        self.assertIn("Insufficient VRAM", reason)

    def test_acceptance_3_recommendations_respect_memory_and_storage(self) -> None:
        """Acceptance Test 3: Recommendations respect configured memory and storage limits."""
        # Low-spec machine: 3.8 GB RAM available, 6 GB disk free
        constrained_report = HardwareReport(
            cpu_architecture="x86_64",
            cpu_cores=2,
            cpu_threads=4,
            ram_total_mb=8192,
            ram_available_mb=3800,
            gpu_name=None,
            gpu_vram_mb=None,
            accelerator_type=None,
            storage_total_mb=128000,
            storage_available_mb=6000,
            supported_runtimes=("llama.cpp", "deterministic-local"),
            installed_applications=frozenset(),
            online=True,
            platform_system="Linux",
        )

        rec = self.registry.recommend(constrained_report)
        self.assertTrue(rec.is_compatible)
        # Small fits in 3800 MB RAM and 6000 MB storage; Medium does not
        self.assertEqual(rec.selected_tier, ModelTier.SMALL)
        self.assertEqual(rec.recommended_model.model_id, "pyflare-small-3b-q4")

    def test_acceptance_4_insufficient_storage_blocks_download_before_start(self) -> None:
        """Acceptance Test 4: Insufficient storage blocks download before initiation."""
        # Model requires 5000 MB disk free, but user only has 1500 MB free
        with self.assertRaises(InsufficientStorageError) as ctx:
            self.registry.preflight_download_check("pyflare-small-3b-q4", storage_available_mb=1500)

        self.assertIn("requires 5000 MB free space", str(ctx.exception))
        self.assertIn("1500 MB is available", str(ctx.exception))

    def test_acceptance_5_invalid_model_metadata_rejected(self) -> None:
        """Acceptance Test 5: Invalid model metadata is rejected at construction."""
        # Negative parameters
        with self.assertRaises(ValueError):
            ModelMetadata(
                model_id="bad-1",
                name="Bad",
                tier=ModelTier.SMALL,
                parameters_billion=-1.0,
                quantization="Q4",
                download_size_mb=100,
                min_ram_mb=500,
                recommended_ram_mb=1000,
                min_vram_mb=0,
                min_disk_free_mb=200,
                context_window_tokens=2048,
                supported_runtimes=("llama.cpp",),
                sha256_checksum="abc",
                source_url="http://x",
            )

        # min_disk_free_mb <= download_size_mb (no safety margin)
        with self.assertRaises(ValueError):
            ModelMetadata(
                model_id="bad-2",
                name="Bad",
                tier=ModelTier.SMALL,
                parameters_billion=1.0,
                quantization="Q4",
                download_size_mb=1000,
                min_ram_mb=500,
                recommended_ram_mb=1000,
                min_vram_mb=0,
                min_disk_free_mb=1000,  # Not greater than download size
                context_window_tokens=2048,
                supported_runtimes=("llama.cpp",),
                sha256_checksum="abc",
                source_url="http://x",
            )

    def test_acceptance_6_user_can_select_api_only(self) -> None:
        """Acceptance Test 6: Users can select API-only operation regardless of hardware."""
        beefy_report = HardwareReport(
            cpu_architecture="x86_64",
            cpu_cores=16,
            cpu_threads=32,
            ram_total_mb=65536,
            ram_available_mb=48000,
            gpu_name="NVIDIA RTX 4090",
            gpu_vram_mb=24576,
            accelerator_type="cuda",
            storage_total_mb=2000000,
            storage_available_mb=1000000,
            supported_runtimes=("llama.cpp", "ollama", "onnxruntime"),
            installed_applications=frozenset(),
            online=True,
            platform_system="Linux",
        )

        rec = self.registry.recommend(beefy_report, api_only=True)
        self.assertEqual(rec.selected_tier, ModelTier.API_ONLY)
        self.assertIsNone(rec.recommended_model)
        self.assertTrue(rec.is_compatible)
        self.assertIn("API-only mode", rec.explanation)

    def test_acceptance_7_model_download_integrity_verification(self) -> None:
        """Acceptance Test 7: Downloaded files are verified via SHA256 integrity check."""
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test_model.gguf"
            content = b"Simulated Model GGUF Content Bytes For PyFlare 2027"
            file_path.write_bytes(content)
            expected_hash = hashlib.sha256(content).hexdigest()

            # Exact match succeeds
            self.assertTrue(
                ModelCapabilityRegistry.verify_file_integrity(file_path, expected_hash)
            )

            # Corrupted / tampered file fails
            self.assertFalse(
                ModelCapabilityRegistry.verify_file_integrity(file_path, "0" * 64)
            )

            # Non-existent file fails cleanly
            self.assertFalse(
                ModelCapabilityRegistry.verify_file_integrity(Path(tmp_dir) / "missing.gguf", expected_hash)
            )


if __name__ == "__main__":
    unittest.main()
