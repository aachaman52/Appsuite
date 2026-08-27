"""Pydantic data models for PyFlare's Deterministic Routing Layer."""
from __future__ import annotations

import enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskType(str, enum.Enum):
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    RESEARCH = "research"
    IMAGE_GENERATION = "image_generation"
    THREE_D_GENERATION = "3d_generation"
    BLENDER_AUTOMATION = "blender_automation"
    GODOT_AUTOMATION = "godot_automation"
    ASSET_PROCESSING = "asset_processing"
    VALIDATION = "validation"
    DEPLOYMENT = "deployment"
    GENERAL = "general"


class PrivacyLevel(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class HardwareTier(str, enum.Enum):
    WEAK = "weak"
    MID = "mid"
    HIGH = "high"


class CapabilityRequirement(BaseModel):
    capability_name: str
    min_level: float = 1.0
    is_required: bool = True


class ProviderCapability(BaseModel):
    capability_name: str
    level: float = 1.0
    description: str = ""


class HardwareProfile(BaseModel):
    cpu_cores_logical: int = 1
    cpu_cores_physical: int = 1
    ram_total_mb: float = 8192.0
    ram_available_mb: float = 4096.0
    gpu_name: Optional[str] = None
    vram_total_mb: float = 0.0
    vram_available_mb: float = 0.0
    disk_available_gb: float = 20.0
    os_name: str = "windows"
    hardware_tier: HardwareTier = HardwareTier.MID
    installed_binaries: Dict[str, bool] = Field(default_factory=dict)
    resource_pressure: Dict[str, float] = Field(default_factory=dict)


class ExecutionConstraint(BaseModel):
    allow_cloud: bool = True
    require_local: bool = False
    max_cost_usd: Optional[float] = None
    max_latency_seconds: Optional[float] = None
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL


class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    prompt: str
    task_type: TaskType = TaskType.GENERAL
    required_capabilities: List[str] = Field(default_factory=list)
    optional_capabilities: List[str] = Field(default_factory=list)
    privacy_level: PrivacyLevel = PrivacyLevel.PUBLIC
    max_cost_usd: Optional[float] = None
    preferred_latency_seconds: Optional[float] = None
    min_quality_score: float = 0.0
    allow_cloud: bool = True
    require_local: bool = False
    required_tools: List[str] = Field(default_factory=list)
    estimated_ram_mb: float = 256.0
    estimated_vram_mb: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RouteCandidate(BaseModel):
    candidate_id: str
    provider_type: str
    display_name: str
    is_local: bool = False
    privacy_level: PrivacyLevel = PrivacyLevel.PUBLIC
    estimated_cost_usd: float = 0.0
    expected_latency_seconds: float = 1.0
    quality_score: float = 0.8
    min_ram_mb: float = 256.0
    min_vram_mb: float = 0.0
    required_api_key_env: Optional[str] = None
    required_executable: Optional[str] = None
    concurrency_limit: int = 4
    supported_task_types: List[TaskType] = Field(default_factory=list)
    capabilities: List[ProviderCapability] = Field(default_factory=list)
    is_available: bool = True
    unavailability_reason: Optional[str] = None
    supported_input_formats: List[str] = Field(default_factory=lambda: ["text/plain", "application/json"])
    supported_output_formats: List[str] = Field(default_factory=lambda: ["text/plain", "application/json"])


class RouteDecision(BaseModel):
    task_id: str
    selected_candidate: Optional[RouteCandidate] = None
    score: float = 0.0
    selection_reasons: List[str] = Field(default_factory=list)
    fallback_candidates: List[RouteCandidate] = Field(default_factory=list)
    accepted_candidates: List[RouteCandidate] = Field(default_factory=list)
    rejected_candidates: Dict[str, str] = Field(default_factory=dict)
    candidate_scores: Dict[str, float] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    estimated_latency_seconds: float = 0.0
    hardware_profile_summary: Dict[str, Any] = Field(default_factory=dict)


class RouteOutcome(BaseModel):
    task_id: str
    candidate_id: str
    task_type: TaskType
    success: bool
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    validation_score: float = 1.0
    hardware_tier: HardwareTier = HardwareTier.MID
    timestamp: float = 0.0
