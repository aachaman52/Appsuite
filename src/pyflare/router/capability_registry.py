"""Capability Registry for PyFlare Deterministic Router."""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from pyflare.router.models import (
    PrivacyLevel,
    ProviderCapability,
    RouteCandidate,
    TaskType,
)


class CapabilityRegistry:
    """Central registry of all provider, model, and worker route candidates."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._candidates: Dict[str, RouteCandidate] = {}
        self._register_default_candidates()

    def register_candidate(self, candidate: RouteCandidate) -> None:
        """Register or update a route candidate."""
        self._candidates[candidate.candidate_id] = candidate

    def get_candidate(self, candidate_id: str) -> Optional[RouteCandidate]:
        """Retrieve candidate by ID."""
        return self._candidates.get(candidate_id)

    def list_candidates(self) -> List[RouteCandidate]:
        """Return all registered candidates evaluated for current environment availability."""
        # Refresh availability dynamically
        return [self._evaluate_availability(c) for c in self._candidates.values()]

    def get_available_candidates_for_task(self, task_type: TaskType) -> List[RouteCandidate]:
        """Return all registered candidates that support a given task type."""
        candidates = self.list_candidates()
        return [c for c in candidates if task_type in c.supported_task_types or TaskType.GENERAL in c.supported_task_types]

    def _evaluate_availability(self, candidate: RouteCandidate) -> RouteCandidate:
        """Dynamically evaluate API key and executable availability."""
        cand = candidate.model_copy()

        # Check required API key
        if cand.required_api_key_env:
            key_val = os.environ.get(cand.required_api_key_env)
            if not key_val:
                cand.is_available = False
                cand.unavailability_reason = f"Missing environment variable: {cand.required_api_key_env}"
                return cand

        cand.is_available = True
        cand.unavailability_reason = None
        return cand

    def _register_default_candidates(self) -> None:
        """Register the built-in system candidates."""
        # 1. OpenAI Cloud
        self.register_candidate(RouteCandidate(
            candidate_id="openai-cloud",
            provider_type="cloud_llm",
            display_name="OpenAI GPT-4o / Cloud LLM",
            is_local=False,
            privacy_level=PrivacyLevel.PUBLIC,
            estimated_cost_usd=0.015,
            expected_latency_seconds=1.8,
            quality_score=0.95,
            min_ram_mb=128.0,
            min_vram_mb=0.0,
            required_api_key_env="OPENAI_API_KEY",
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
                TaskType.RESEARCH,
                TaskType.GENERAL,
                TaskType.VALIDATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="code_synthesis", level=0.95),
                ProviderCapability(capability_name="reasoning", level=0.95),
                ProviderCapability(capability_name="json_schema", level=1.0),
            ],
        ))

        # 2. Google Gemini Cloud
        self.register_candidate(RouteCandidate(
            candidate_id="gemini-cloud",
            provider_type="cloud_llm",
            display_name="Google Gemini 1.5 Pro",
            is_local=False,
            privacy_level=PrivacyLevel.PUBLIC,
            estimated_cost_usd=0.008,
            expected_latency_seconds=1.5,
            quality_score=0.92,
            min_ram_mb=128.0,
            min_vram_mb=0.0,
            required_api_key_env="GEMINI_API_KEY",
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
                TaskType.RESEARCH,
                TaskType.GENERAL,
                TaskType.IMAGE_GENERATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="code_synthesis", level=0.92),
                ProviderCapability(capability_name="multimodal_reasoning", level=0.95),
                ProviderCapability(capability_name="long_context", level=1.0),
            ],
        ))

        # 3. Anthropic Claude Cloud
        self.register_candidate(RouteCandidate(
            candidate_id="claude-cloud",
            provider_type="cloud_llm",
            display_name="Anthropic Claude 3.5 Sonnet",
            is_local=False,
            privacy_level=PrivacyLevel.PUBLIC,
            estimated_cost_usd=0.015,
            expected_latency_seconds=2.0,
            quality_score=0.98,
            min_ram_mb=128.0,
            min_vram_mb=0.0,
            required_api_key_env="ANTHROPIC_API_KEY",
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
                TaskType.RESEARCH,
                TaskType.GENERAL,
                TaskType.VALIDATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="code_synthesis", level=0.98),
                ProviderCapability(capability_name="architecture_design", level=0.98),
            ],
        ))

        # 4. Local OpenAI-Compatible LLM (Ollama / Local Server)
        self.register_candidate(RouteCandidate(
            candidate_id="local-llm",
            provider_type="local_llm",
            display_name="Local LLM (OpenAI-Compatible)",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=3.5,
            quality_score=0.78,
            min_ram_mb=4096.0,
            min_vram_mb=2048.0,
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
                TaskType.GENERAL,
                TaskType.VALIDATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="code_synthesis", level=0.75),
                ProviderCapability(capability_name="local_privacy", level=1.0),
            ],
        ))

        # 5. Local Fallback Rules Generator (always available zero-cost baseline)
        self.register_candidate(RouteCandidate(
            candidate_id="local-fallback-rules",
            provider_type="local_rules",
            display_name="Local Deterministic Rule Engine",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=0.05,
            quality_score=0.60,
            min_ram_mb=64.0,
            min_vram_mb=0.0,
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
                TaskType.GENERAL,
                TaskType.ASSET_PROCESSING,
                TaskType.VALIDATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="deterministic_rules", level=1.0),
                ProviderCapability(capability_name="local_privacy", level=1.0),
            ],
        ))

        # 6. Blender Worker
        self.register_candidate(RouteCandidate(
            candidate_id="blender-worker",
            provider_type="local_worker",
            display_name="Blender 3D Automation Engine",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=5.0,
            quality_score=0.90,
            min_ram_mb=2048.0,
            min_vram_mb=0.0,
            required_executable="blender",
            supported_task_types=[
                TaskType.THREE_D_GENERATION,
                TaskType.BLENDER_AUTOMATION,
                TaskType.ASSET_PROCESSING,
            ],
            capabilities=[
                ProviderCapability(capability_name="3d_mesh_generation", level=0.88),
                ProviderCapability(capability_name="fbx_export", level=0.95),
                ProviderCapability(capability_name="material_assignment", level=0.90),
            ],
        ))

        # 7. Godot Worker
        self.register_candidate(RouteCandidate(
            candidate_id="godot-worker",
            provider_type="local_worker",
            display_name="Godot 4 Scene & Project Synthesizer",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=3.0,
            quality_score=0.92,
            min_ram_mb=1536.0,
            min_vram_mb=256.0,
            required_executable="godot",
            supported_task_types=[
                TaskType.GODOT_AUTOMATION,
                TaskType.ASSET_PROCESSING,
                TaskType.VALIDATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="tscn_generation", level=0.95),
                ProviderCapability(capability_name="gdscript_integration", level=0.90),
            ],
        ))

        # 8. Internet Worker
        self.register_candidate(RouteCandidate(
            candidate_id="internet-worker",
            provider_type="network_worker",
            display_name="Internet & Asset Search Worker",
            is_local=False,
            privacy_level=PrivacyLevel.PUBLIC,
            estimated_cost_usd=0.0,
            expected_latency_seconds=2.5,
            quality_score=0.85,
            min_ram_mb=512.0,
            min_vram_mb=0.0,
            supported_task_types=[
                TaskType.RESEARCH,
                TaskType.ASSET_PROCESSING,
            ],
            capabilities=[
                ProviderCapability(capability_name="asset_search", level=0.90),
                ProviderCapability(capability_name="web_scraping", level=0.85),
            ],
        ))

        # 9. Validation Worker
        self.register_candidate(RouteCandidate(
            candidate_id="validation-worker",
            provider_type="local_worker",
            display_name="Static Analysis & Asset Validator",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=0.8,
            quality_score=0.95,
            min_ram_mb=256.0,
            min_vram_mb=0.0,
            supported_task_types=[
                TaskType.VALIDATION,
                TaskType.CODE_ANALYSIS,
            ],
            capabilities=[
                ProviderCapability(capability_name="syntax_verification", level=1.0),
                ProviderCapability(capability_name="scene_integrity", level=0.92),
            ],
        ))

        # 10. Code Worker
        self.register_candidate(RouteCandidate(
            candidate_id="code-worker",
            provider_type="hybrid_worker",
            display_name="PyFlare Code Synthesis Worker",
            is_local=True,
            privacy_level=PrivacyLevel.INTERNAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=1.2,
            quality_score=0.88,
            min_ram_mb=512.0,
            min_vram_mb=0.0,
            supported_task_types=[
                TaskType.CODE_GENERATION,
                TaskType.CODE_ANALYSIS,
            ],
            capabilities=[
                ProviderCapability(capability_name="gdscript_generation", level=0.90),
                ProviderCapability(capability_name="python_generation", level=0.90),
            ],
        ))

        # 11. Deploy Worker
        self.register_candidate(RouteCandidate(
            candidate_id="deploy-worker",
            provider_type="deployment_worker",
            display_name="Cloud & Local Packager/Deployer",
            is_local=True,
            privacy_level=PrivacyLevel.INTERNAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=2.0,
            quality_score=0.90,
            min_ram_mb=512.0,
            min_vram_mb=0.0,
            supported_task_types=[
                TaskType.DEPLOYMENT,
            ],
            capabilities=[
                ProviderCapability(capability_name="zip_packaging", level=1.0),
                ProviderCapability(capability_name="html5_export", level=0.90),
            ],
        ))

        # 12. Meshy 3D External Cloud Provider (3D Generation)
        self.register_candidate(RouteCandidate(
            candidate_id="meshy-3d",
            provider_type="cloud_3d",
            display_name="Meshy 3D Cloud API",
            is_local=False,
            privacy_level=PrivacyLevel.PUBLIC,
            estimated_cost_usd=0.05,
            expected_latency_seconds=12.0,
            quality_score=0.92,
            min_ram_mb=256.0,
            min_vram_mb=0.0,
            required_api_key_env="MESHY_API_KEY",
            supported_task_types=[
                TaskType.THREE_D_GENERATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="text_to_3d", level=0.95),
                ProviderCapability(capability_name="textured_glb", level=0.90),
            ],
        ))

        # 13. Local 3D Generation Model (Tripo / Shap-E / Point-E)
        self.register_candidate(RouteCandidate(
            candidate_id="local-3d-model",
            provider_type="local_3d",
            display_name="Local Text-to-3D Neural Model",
            is_local=True,
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            estimated_cost_usd=0.0,
            expected_latency_seconds=15.0,
            quality_score=0.82,
            min_ram_mb=8192.0,
            min_vram_mb=4096.0,
            supported_task_types=[
                TaskType.THREE_D_GENERATION,
            ],
            capabilities=[
                ProviderCapability(capability_name="local_text_to_3d", level=0.82),
                ProviderCapability(capability_name="local_privacy", level=1.0),
            ],
        ))
