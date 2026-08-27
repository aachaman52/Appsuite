"""Worker Health Monitor for checking system dependencies and doctor checks."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None


def run_doctor_checks(config: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Execute preflight diagnostic checks on runtime environment.
    """
    checks: List[Dict[str, Any]] = []

    # 1. Python runtime check
    py_ok = sys.version_info >= (3, 11)
    checks.append({
        "title": "Python Runtime",
        "ok": py_ok,
        "required": True,
        "message": f"Python {sys.version.split()[0]} ({'Supported >= 3.11' if py_ok else 'Requires >= 3.11'})",
    })

    # 2. RAM availability check
    if psutil:
        mem = psutil.virtual_memory()
        ram_ok = mem.available >= 200 * 1024 * 1024
        checks.append({
            "title": "Available RAM",
            "ok": ram_ok,
            "required": False,
            "message": f"{mem.available / (1024 * 1024):.1f} MB available (Total: {mem.total / (1024 * 1024):.1f} MB)",
        })
    else:
        checks.append({
            "title": "Memory Monitor (psutil)",
            "ok": False,
            "required": False,
            "message": "psutil not available; hardware profiling falling back to standard estimates",
        })

    # 3. Disk space check
    try:
        total, used, free = shutil.disk_usage(".")
        disk_ok = free >= 500 * 1024 * 1024
        checks.append({
            "title": "Workspace Disk Space",
            "ok": disk_ok,
            "required": True,
            "message": f"{free / (1024 * 1024 * 1024):.1f} GB free",
        })
    except Exception as exc:
        checks.append({
            "title": "Workspace Disk Space",
            "ok": False,
            "required": True,
            "message": f"Failed to inspect disk usage: {exc}",
        })

    return checks


class WorkerHealthMonitor:
    def __init__(self, config: Optional[Any] = None) -> None:
        self.config = config

    @staticmethod
    def preflight_check(worker_type: str) -> Tuple[bool, str]:
        """
        Checks system health and dependencies before allowing a worker to run.
        Returns (is_healthy, reason).
        """
        # 1. Check RAM
        if psutil:
            mem = psutil.virtual_memory()
            if mem.available < 10 * 1024 * 1024:
                return False, "DEPENDENCY_MISSING: INSUFFICIENT_RAM"

        # 2. Check Disk Space
        try:
            total, used, free = shutil.disk_usage(".")
            if free < 100 * 1024 * 1024:
                return False, "DEPENDENCY_MISSING: INSUFFICIENT_DISK_SPACE"
        except Exception:
            pass

        # 3. Worker-specific binary checks
        from .config import load_config
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
