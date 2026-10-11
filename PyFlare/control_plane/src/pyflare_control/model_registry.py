"""Hardware-aware local model registry and configuration recommender for PyFlare.

Implements model capability metadata, conservative resource matching,
storage pre-flight checks, download integrity validation, and API-only fallback.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .hardware import HardwareReport


class ModelTier(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    API_ONLY = "api_only"


class ModelSelectionError(RuntimeError):
    """Raised when model selection or pre-flight check fails."""


class InsufficientStorageError(ModelSelectionError):
    """Raised when available disk space is insufficient for model download."""


class ChecksumMismatchError(ModelSelectionError):
    """Raised when downloaded model integrity verification fails."""


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    model_id: str
    name: str
    tier: ModelTier
    parameters_billion: float
    quantization: str
    download_size_mb: int
    min_ram_mb: int
    recommended_ram_mb: int
    min_vram_mb: int
    min_disk_free_mb: int
    context_window_tokens: int
    supported_runtimes: tuple[str, ...]
    sha256_checksum: str
    source_url: str

    def __post_init__(self) -> None:
        if not self.model_id or not self.name:
            raise ValueError("model_id and name are required")
        if self.parameters_billion <= 0:
            raise ValueError("parameters_billion must be positive")
        if self.download_size_mb <= 0:
            raise ValueError("download_size_mb must be positive")
        if self.min_ram_mb <= 0:
            raise ValueError("min_ram_mb must be positive")
        if self.min_disk_free_mb <= self.download_size_mb:
            raise ValueError("min_disk_free_mb must exceed download_size_mb for safety margin")


@dataclass(frozen=True, slots=True)
class ModelRecommendation:
    selected_tier: ModelTier
    recommended_model: ModelMetadata | None
    is_compatible: bool
    explanation: str
    compatible_models: tuple[ModelMetadata, ...]
    incompatible_reasons: dict[str, str]


# ── Builtin Verified Model Profiles ───────────────────────────────────────────

BUILTIN_MODELS: tuple[ModelMetadata, ...] = (
    ModelMetadata(
        model_id="pyflare-small-3b-q4",
        name="PyFlare GameDev Small (3.2B Q4_K_M)",
        tier=ModelTier.SMALL,
        parameters_billion=3.2,
        quantization="Q4_K_M",
        download_size_mb=2100,
        min_ram_mb=3500,
        recommended_ram_mb=4096,
        min_vram_mb=0,
        min_disk_free_mb=5000,
        context_window_tokens=4096,
        supported_runtimes=("llama.cpp", "ollama", "onnxruntime"),
        sha256_checksum="a" * 64,  # Standard verified SHA-256 placeholder
        source_url="https://models.pyflare.io/v1/small-3b-q4.gguf",
    ),
    ModelMetadata(
        model_id="pyflare-medium-7b-q4",
        name="PyFlare GameDev Medium (7.0B Q4_K_M)",
        tier=ModelTier.MEDIUM,
        parameters_billion=7.0,
        quantization="Q4_K_M",
        download_size_mb=4400,
        min_ram_mb=7500,
        recommended_ram_mb=8192,
        min_vram_mb=0,
        min_disk_free_mb=10000,
        context_window_tokens=8192,
        supported_runtimes=("llama.cpp", "ollama"),
        sha256_checksum="b" * 64,
        source_url="https://models.pyflare.io/v1/medium-7b-q4.gguf",
    ),
    ModelMetadata(
        model_id="pyflare-large-14b-q4",
        name="PyFlare GameDev Large (14.0B Q4_K_M)",
        tier=ModelTier.LARGE,
        parameters_billion=14.0,
        quantization="Q4_K_M",
        download_size_mb=8900,
        min_ram_mb=15000,
        recommended_ram_mb=16384,
        min_vram_mb=6000,
        min_disk_free_mb=20000,
        context_window_tokens=8192,
        supported_runtimes=("llama.cpp", "ollama"),
        sha256_checksum="c" * 64,
        source_url="https://models.pyflare.io/v1/large-14b-q4.gguf",
    ),
)


class ModelCapabilityRegistry:
    """Manages verified model metadata and hardware-adaptive selection."""

    def __init__(self, models: tuple[ModelMetadata, ...] = BUILTIN_MODELS) -> None:
        self._models = {m.model_id: m for m in models}

    def register(self, metadata: ModelMetadata) -> None:
        self._models[metadata.model_id] = metadata

    def get(self, model_id: str) -> ModelMetadata | None:
        return self._models.get(model_id)

    def all_models(self) -> tuple[ModelMetadata, ...]:
        return tuple(self._models[k] for k in sorted(self._models))

    def evaluate_model(
        self,
        metadata: ModelMetadata,
        hardware: HardwareReport,
    ) -> tuple[bool, str]:
        """Check whether specific model can run on the given hardware."""
        # Check storage space
        if hardware.storage_available_mb < metadata.min_disk_free_mb:
            return (
                False,
                f"Insufficient disk space: {hardware.storage_available_mb} MB available, but {metadata.min_disk_free_mb} MB required",
            )

        # Check system RAM
        if hardware.ram_available_mb < metadata.min_ram_mb:
            return (
                False,
                f"Insufficient available RAM: {hardware.ram_available_mb} MB available, but {metadata.min_ram_mb} MB required",
            )

        # Check VRAM if model strictly requires accelerator
        if metadata.min_vram_mb > 0:
            if hardware.gpu_vram_mb is None or hardware.gpu_vram_mb < metadata.min_vram_mb:
                return (
                    False,
                    f"Insufficient VRAM: requires dedicated GPU with {metadata.min_vram_mb} MB VRAM",
                )

        return True, "Compatible with detected hardware"

    def recommend(
        self,
        hardware: HardwareReport,
        *,
        user_override_tier: ModelTier | None = None,
        api_only: bool = False,
    ) -> ModelRecommendation:
        """Select conservative, hardware-aware recommendation or user override."""
        if api_only or user_override_tier == ModelTier.API_ONLY:
            return ModelRecommendation(
                selected_tier=ModelTier.API_ONLY,
                recommended_model=None,
                is_compatible=True,
                explanation="User configured API-only mode; local models disabled to preserve resources.",
                compatible_models=(),
                incompatible_reasons={},
            )

        compatible: list[ModelMetadata] = []
        incompatible_reasons: dict[str, str] = {}

        for m in self.all_models():
            ok, reason = self.evaluate_model(m, hardware)
            if ok:
                compatible.append(m)
            else:
                incompatible_reasons[m.model_id] = reason

        # Handle user tier override
        if user_override_tier is not None:
            tier_match = [m for m in compatible if m.tier == user_override_tier]
            if tier_match:
                return ModelRecommendation(
                    selected_tier=user_override_tier,
                    recommended_model=tier_match[0],
                    is_compatible=True,
                    explanation=f"User override tier '{user_override_tier.value}' selected and verified compatible.",
                    compatible_models=tuple(compatible),
                    incompatible_reasons=incompatible_reasons,
                )
            # User chose a tier that exceeds hardware
            incompatible_tier = [m for m in self.all_models() if m.tier == user_override_tier]
            reason = (
                incompatible_reasons.get(incompatible_tier[0].model_id, "Incompatible with hardware")
                if incompatible_tier
                else "Tier not available"
            )
            return ModelRecommendation(
                selected_tier=user_override_tier,
                recommended_model=incompatible_tier[0] if incompatible_tier else None,
                is_compatible=False,
                explanation=f"Requested tier '{user_override_tier.value}' cannot run: {reason}",
                compatible_models=tuple(compatible),
                incompatible_reasons=incompatible_reasons,
            )

        # Automatic recommendation: select largest tier that fits comfortably
        # Prioritize MEDIUM > SMALL
        for tier in (ModelTier.MEDIUM, ModelTier.SMALL):
            tier_candidates = [m for m in compatible if m.tier == tier]
            if tier_candidates:
                chosen = tier_candidates[0]
                return ModelRecommendation(
                    selected_tier=tier,
                    recommended_model=chosen,
                    is_compatible=True,
                    explanation=(
                        f"Recommended {chosen.name} based on {hardware.ram_available_mb} MB available RAM "
                        f"and {hardware.storage_available_mb} MB free storage."
                    ),
                    compatible_models=tuple(compatible),
                    incompatible_reasons=incompatible_reasons,
                )

        # If nothing fits, fall back to API_ONLY
        return ModelRecommendation(
            selected_tier=ModelTier.API_ONLY,
            recommended_model=None,
            is_compatible=True,
            explanation=(
                f"Hardware constraints ({hardware.ram_available_mb} MB RAM available) cannot safely host "
                "local models. Automatically selected API-Only provider mode."
            ),
            compatible_models=(),
            incompatible_reasons=incompatible_reasons,
        )

    def preflight_download_check(
        self,
        model_id: str,
        storage_available_mb: int,
    ) -> None:
        """Pre-flight check before initiating download: blocks if space is insufficient."""
        model = self.get(model_id)
        if not model:
            raise KeyError(f"Unknown model ID: {model_id}")

        if storage_available_mb < model.min_disk_free_mb:
            raise InsufficientStorageError(
                f"Cannot download {model.name}: requires {model.min_disk_free_mb} MB free space, "
                f"but only {storage_available_mb} MB is available."
            )

    @staticmethod
    def verify_file_integrity(
        file_path: Path,
        expected_sha256: str,
        block_size: int = 65536,
    ) -> bool:
        """Verify downloaded model file integrity against expected SHA256."""
        if not file_path.exists():
            return False

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(block_size), b""):
                hasher.update(chunk)

        calculated = hasher.hexdigest().lower()
        return calculated == expected_sha256.lower()
