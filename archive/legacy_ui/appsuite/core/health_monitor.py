"""
Worker Health Monitor & Dependency Registry
===========================================
Validates worker dependencies at startup to avoid runtime failures.
"""
from __future__ import annotations

import os
import sys
import subprocess
import json
import shutil
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from ..logging_setup import get_structured_logger

log = get_structured_logger("health_monitor")

@dataclass
class WorkerCapability:
    requires: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    version_constraints: Dict[str, str] = field(default_factory=dict)


class WorkerHealthMonitor:
    def __init__(self, config: Any):
        self.config = config
        self.health_status: Dict[str, str] = {}
        
        # Define base capabilities for known workers
        self.registry = {
            "godot": WorkerCapability(requires=["godot"]),
            "blender": WorkerCapability(requires=["blender"]),
            "internet": WorkerCapability(requires=["internet"]),
            "analysis": WorkerCapability(requires=[]),
            "code": WorkerCapability(requires=["internet"]), # Needs API access
            "deploy": WorkerCapability(requires=["internet"]),
            "validation": WorkerCapability(requires=[])
        }

    def check_system(self) -> Dict[str, Any]:
        """Comprehensive system check returning diagnostic data and status"""
        report = {
            "status": "Healthy",
            "checks": {}
        }
        
        has_warning = False
        has_critical = False

        def record(name: str, status: str, detail: str = "", critical: bool = False):
            nonlocal has_warning, has_critical
            report["checks"][name] = {"status": status, "detail": detail}
            if status == "Failed":
                if critical:
                    has_critical = True
                else:
                    has_warning = True

        # Python
        v = sys.version_info
        if v.major >= 3 and v.minor >= 10:
            record("Python", "Passed", f"{v.major}.{v.minor}.{v.micro}")
        else:
            record("Python", "Failed", f"Requires 3.10+, found {v.major}.{v.minor}", critical=True)

        # Git
        git_path = shutil.which("git")
        if git_path:
            record("Git", "Passed", git_path)
        else:
            record("Git", "Failed", "Git not found in PATH", critical=True)

        # Godot & Blender
        godot_bin = self.config.workers.get("godot", {}).get("binary", "godot")
        blender_bin = self.config.workers.get("blender", {}).get("binary", "blender")
        
        if shutil.which(godot_bin) or (os.path.exists(godot_bin) and os.access(godot_bin, os.X_OK)):
            record("Godot", "Passed", godot_bin)
        else:
            record("Godot", "Failed", "Godot 4 not found", critical=True)

        if shutil.which(blender_bin) or (os.path.exists(blender_bin) and os.access(blender_bin, os.X_OK)):
            record("Blender", "Passed", blender_bin)
        else:
            record("Blender", "Failed", "Blender not found", critical=True)

        # CUDA / GPU Driver
        try:
            subprocess.run(["nvidia-smi"], capture_output=True, check=True, timeout=5)
            record("GPU Driver", "Passed", "nvidia-smi found")
            record("CUDA", "Passed", "CUDA available")
        except Exception:
            record("GPU Driver", "Failed", "nvidia-smi not found or failed", critical=False)
            record("CUDA", "Failed", "CUDA not available", critical=False)

        # Internet
        try:
            urllib.request.urlopen("https://1.1.1.1", timeout=2)
            record("Internet", "Passed")
        except Exception:
            record("Internet", "Failed", "No internet access", critical=True)

        # Database
        db_path = self.config.abs_path("database_path")
        if db_path.parent.exists() and os.access(db_path.parent, os.W_OK):
            record("Database", "Passed", str(db_path))
        else:
            record("Database", "Failed", "Database path inaccessible", critical=True)

        # RAM & Disk
        try:
            import psutil
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.config.abs_path("output_dir")))
            
            ram_gb = ram.total / (1024**3)
            if ram.available < 2 * (1024**3):
                record("RAM", "Failed", f"Low RAM available ({ram.available/(1024**3):.1f} GB)", critical=False)
            else:
                record("RAM", "Passed", f"{ram_gb:.1f} GB total")

            if disk.free < 5 * (1024**3):
                record("Disk Space", "Failed", f"Low disk space ({disk.free/(1024**3):.1f} GB)", critical=True)
            else:
                record("Disk Space", "Passed", f"{disk.free/(1024**3):.1f} GB free")
        except ImportError:
            record("RAM", "Warning", "psutil not installed")
            record("Disk Space", "Warning", "psutil not installed")

        # Provider API Keys
        providers = self.config.providers
        if providers:
            record("Provider API Keys", "Passed", f"{len(providers)} providers found")
        else:
            record("Provider API Keys", "Failed", "No API keys configured", critical=True)

        if has_critical:
            report["status"] = "Critical"
        elif has_warning:
            report["status"] = "Warning"

        return report

    def generate_diagnostic_report(self) -> str:
        report = self.check_system()
        lines = [
            f"# AppSuite Health Monitor: {report['status']}",
            ""
        ]
        for name, data in report["checks"].items():
            status = "✅" if data["status"] == "Passed" else ("⚠️" if data["status"] == "Warning" else "❌")
            lines.append(f"- {status} **{name}**: {data['detail']}")
            
        report_path = self.config.abs_path("output_dir") / "health_report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return "\n".join(lines)
