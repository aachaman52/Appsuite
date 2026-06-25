"""API request/response models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, description="Natural language scene description")
    template_id: Optional[str] = Field(None, description="Force a specific template")


class JobResponse(BaseModel):
    id: str
    prompt: str
    status: str
    stage: Optional[str] = None
    progress: float = 0.0
    template_id: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: float
    updated_at: float


class JobEvent(BaseModel):
    stage: Optional[str]
    level: str
    message: str
    created_at: float


class AssetResponse(BaseModel):
    id: str
    role: Optional[str]
    name: Optional[str]
    source: Optional[str]
    format: Optional[str]
    quality_score: Optional[float]
    file_path: Optional[str]


class SystemStatus(BaseModel):
    app: str
    version: str
    uptime_seconds: float
    resources: Dict[str, Any]
    workers: Dict[str, Any]
    jobs: Dict[str, Any]
    providers: List[Dict[str, Any]]