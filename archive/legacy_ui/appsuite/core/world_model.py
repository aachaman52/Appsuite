"""World Model storage and job-local runtime knowledge base."""
from __future__ import annotations

import json
import time
import os
import sys
import shutil
import platform
import psutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..db import Database


class WorldModel:
    """In-memory world state for a single job with SQLite persistence, synchronizing reality with filesystem & system specs."""

    def __init__(self, job_id: str, db: Optional[Database] = None):
        self.job_id = job_id
        self.db = db
        self._state: Dict[str, Any] = {}
        if self.db:
            try:
                self._create_table_if_missing()
                self._load_from_db()
            except Exception:
                pass
        self.sync_all_reality()

    def _create_table_if_missing(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS world_model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT,
                updated_at REAL NOT NULL,
                UNIQUE(job_id, key)
            );
            """
        )

    def _load_from_db(self) -> None:
        if not self.db:
            return
        rows = self.db.get_world_model_entries(self.job_id)
        for row in rows:
            if row.get("key"):
                self._state[row["key"]] = row.get("value")

    def update(self, key: str, value: Any) -> None:
        self._state[key] = value
        if self.db:
            try:
                self.db.add_world_model_entry(self.job_id, key, value)
            except Exception:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._state)

    def keys(self) -> list[str]:
        return list(self._state.keys())

    def items(self) -> list[tuple[str, Any]]:
        return list(self._state.items())

    # --- Reality Sync Upgrade ------------------------------------------------
    def sync_all_reality(self, project_dir: Optional[Path] = None) -> None:
        """Runs the synchronization checklist covering hardware, environment, software, and filesystems."""
        self.sync_available_hardware()
        self.sync_environment()
        self.sync_installed_software()
        if project_dir:
            self.sync_filesystem_state(project_dir)

    def sync_filesystem_state(self, directory: Path) -> None:
        """Scans the directory structure and gathers names, sizes, and file extension distribution."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return
            
        fs_info = {
            "root_path": str(dir_path.resolve()),
            "files": [],
            "directories": [],
            "file_count": 0,
            "total_size_bytes": 0
        }
        
        try:
            for root, dirs, files in os.walk(dir_path):
                for d in dirs:
                    fs_info["directories"].append(str(Path(root, d).relative_to(dir_path)))
                for f in files:
                    fp = Path(root, f)
                    try:
                        sz = fp.stat().st_size
                    except Exception:
                        sz = 0
                    fs_info["files"].append({
                        "rel_path": str(fp.relative_to(dir_path)),
                        "size_bytes": sz,
                        "suffix": fp.suffix
                    })
                    fs_info["file_count"] += 1
                    fs_info["total_size_bytes"] += sz
        except Exception:
            pass
            
        self.update("filesystem_state", fs_info)

    def sync_environment(self) -> None:
        """Captures Python version, platform OS name, system path, and environment variables keys."""
        env_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "os": platform.system(),
            "env_keys": list(os.environ.keys()),
            "cwd": os.getcwd()
        }
        self.update("environment_state", env_info)

    def sync_installed_software(self) -> None:
        """Validates if standard binaries like blender, godot, or git are in PATH."""
        software_status = {
            "git": bool(shutil.which("git")),
            "blender": bool(shutil.which("blender")),
            "godot": bool(shutil.which("godot")),
            "python": bool(shutil.which("python") or shutil.which("py"))
        }
        self.update("software_state", software_status)

    def sync_available_hardware(self) -> None:
        """Gathers runtime CPU cores, memory limits, and disk space."""
        try:
            cpu_count = psutil.cpu_count(logical=True)
            vmem = psutil.virtual_memory()
            disk = psutil.disk_usage(".")
            hardware = {
                "cpu_cores": cpu_count,
                "total_memory_mb": vmem.total // (1024 * 1024),
                "available_memory_mb": vmem.available // (1024 * 1024),
                "disk_free_gb": disk.free // (1024 * 1024 * 1024)
            }
        except Exception:
            hardware = {
                "cpu_cores": os.cpu_count() or 1,
                "total_memory_mb": 1024,
                "available_memory_mb": 512,
                "disk_free_gb": 10
            }
        self.update("hardware_state", hardware)
