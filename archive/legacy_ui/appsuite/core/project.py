from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

class Project:
    """Project-based workflow manager. Defines and initializes the project folder structure:
    Project/
    ├── project.godot
    ├── Assets/
    ├── Scenes/
    ├── Outputs/
    ├── Jobs/
    ├── Cache/
    └── History/
    """
    def __init__(self, name: str, base_dir: Path):
        self.name = name
        self.base_dir = Path(base_dir) / name
        self.assets_dir = self.base_dir / "Assets"
        self.scenes_dir = self.base_dir / "Scenes"
        self.outputs_dir = self.base_dir / "Outputs"
        self.jobs_dir = self.base_dir / "Jobs"
        self.cache_dir = self.base_dir / "Cache"
        self.history_dir = self.base_dir / "History"

    def setup_directories(self) -> None:
        """Create project directory structure and write .gdignore to non-Godot directories."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        # Write .gdignore to directories that Godot should not scan
        for d in [self.outputs_dir, self.jobs_dir, self.cache_dir, self.history_dir]:
            (d / ".gdignore").touch()

    def get_godot_project_path(self) -> Path:
        return self.base_dir

    def get_state_dict(self) -> Dict[str, str]:
        return {
            "project_name": self.name,
            "project_path": str(self.base_dir),
            "assets_path": str(self.assets_dir),
            "scenes_path": str(self.scenes_dir),
            "outputs_path": str(self.outputs_dir),
            "jobs_path": str(self.jobs_dir),
            "cache_path": str(self.cache_dir),
            "history_path": str(self.history_dir),
        }
