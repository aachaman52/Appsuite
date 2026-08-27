"""JobState and WorkerStatus definitions to strictly control pipeline state."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# Late import for type checking if needed, but we can just use Any for project if needed to avoid circular imports.
# For runtime, we can just use typing.Any.


class WorkerStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NEED_ASSET = "need_asset"
    NEED_RETRY = "need_retry"
    SKIP = "skip"


@dataclass
class WorkerResult:
    status: WorkerStatus
    data: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobState:
    """
    Strictly controlled state object for the pipeline.
    Supports dictionary-like access to avoid rewriting all workers.
    """
    template: Dict[str, Any]
    assets: List[Dict[str, Any]] = field(default_factory=list)
    normalized_assets: List[Any] = field(default_factory=list)
    project: Any = None  # Project instance
    
    # Project paths
    project_name: str = ""
    project_path: str = ""
    assets_path: str = ""
    scenes_path: str = ""
    outputs_path: str = ""
    jobs_path: str = ""
    cache_path: str = ""
    history_path: str = ""
    
    # Worker outputs
    scene_layout: Dict[str, Any] = field(default_factory=dict)
    fbx_path: Optional[str] = None
    godot_project: Optional[str] = None
    main_scene: Optional[str] = None
    validation: Dict[str, Any] = field(default_factory=dict)
    deployment_url: Optional[str] = None
    generated_scripts: List[Dict[str, Any]] = field(default_factory=list)
    stages: Dict[str, Any] = field(default_factory=dict)
    
    # Attached runtime/world model state for this job
    world_model: Any = None
    
    # For future extensions
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: Any) -> Any:
        if not isinstance(key, str):
            raise KeyError(f"JobState has no key: {key}")
        if not hasattr(self, key):
            raise KeyError(f"JobState has no key: {key}")
        return getattr(self, key)
        
    def __setitem__(self, key: Any, value: Any) -> None:
        if not isinstance(key, str):
            raise KeyError(f"JobState key must be a string: {key}")
        if not hasattr(self, key):
            raise KeyError(f"JobState does not support dynamic key: {key}. Please define it in JobState.")
        setattr(self, key, value)

    def __contains__(self, key: Any) -> bool:
        if not isinstance(key, str):
            return False
        return hasattr(self, key)
        
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def update(self, d: Dict[str, Any]) -> None:
        for k, v in d.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise KeyError(f"JobState does not support dynamic key: {k} during update.")

    def as_dict(self) -> Dict[str, Any]:
        """Convert state back to a plain dictionary for serialization if needed."""
        world_model_state = None
        if hasattr(self.world_model, "to_dict"):
            try:
                world_model_state = self.world_model.to_dict()
            except Exception:
                world_model_state = None
        elif isinstance(self.world_model, dict):
            world_model_state = self.world_model

        return {
            "template": self.template,
            "assets": self.assets,
            "normalized_assets": self.normalized_assets,
            "project_name": self.project_name,
            "project_path": self.project_path,
            "assets_path": self.assets_path,
            "scenes_path": self.scenes_path,
            "outputs_path": self.outputs_path,
            "jobs_path": self.jobs_path,
            "cache_path": self.cache_path,
            "history_path": self.history_path,
            "fbx_path": self.fbx_path,
            "godot_project": self.godot_project,
            "main_scene": self.main_scene,
            "validation": self.validation,
            "deployment_url": self.deployment_url,
            "generated_scripts": self.generated_scripts,
            "stages": self.stages,
            "world_model_state": world_model_state,
            "metadata": self.metadata,
        }
