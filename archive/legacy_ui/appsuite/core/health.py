"""Worker Health Monitor for checking system dependencies before execution."""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Tuple

try:
    import psutil
except ImportError:
    psutil = None

class WorkerHealthMonitor:
    @staticmethod
    def preflight_check(worker_type: str) -> Tuple[bool, str]:
        """
        Checks system health and dependencies before allowing a worker to run.
        Returns (is_healthy, reason).
        """
        # 1. Check RAM (requires 10MB free)
        if psutil:
            mem = psutil.virtual_memory()
            if mem.available < 10 * 1024 * 1024:
                return False, "DEPENDENCY_MISSING: INSUFFICIENT_RAM"
                
        # 2. Check Disk Space (requires 100MB free in temp/cwd)
        total, used, free = shutil.disk_usage(".")
        if free < 100 * 1024 * 1024:
            return False, "DEPENDENCY_MISSING: INSUFFICIENT_DISK_SPACE"
            
        # 3. Worker-specific binary checks
        from ..config import load_config
        cfg = load_config()
        if worker_type == "blender":
            blender_path = os.environ.get("BLENDER_PATH", cfg.raw.get("workers", {}).get("blender", {}).get("binary", "blender"))
            if not shutil.which(blender_path) and not Path(blender_path).exists():
                return False, "DEPENDENCY_MISSING: BLENDER_NOT_FOUND"
                
        elif worker_type == "godot":
            godot_path = os.environ.get("GODOT_PATH", cfg.raw.get("workers", {}).get("godot", {}).get("binary", "godot"))
            if not shutil.which(godot_path) and not Path(godot_path).exists():
                return False, "DEPENDENCY_MISSING: GODOT_NOT_FOUND"
                
        return True, "OK"
