"""
Worker Health Monitor & Dependency Registry
===========================================
Validates worker dependencies at startup to avoid runtime failures.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from ..logging_setup import get_logger

log = get_logger("health_monitor")

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

    def _check_binary(self, name: str, config_key: str) -> bool:
        """Checks if a required binary exists and is executable."""
        # Try finding in config first
        try:
            worker_cfg = self.config.get("workers", {}).get(name, {})
            binary_path = worker_cfg.get("binary_path")
        except AttributeError:
            binary_path = None

        if binary_path and os.path.exists(binary_path) and os.access(binary_path, os.X_OK):
            return True

        # Fallback to PATH check
        try:
            subprocess.run([name, "--version"], capture_output=True, timeout=2, check=False)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_internet(self) -> bool:
        """Ping a highly available endpoint to verify connectivity."""
        try:
            import urllib.request
            urllib.request.urlopen("https://1.1.1.1", timeout=2)
            return True
        except Exception:
            return False

    def run_preflight(self) -> Dict[str, str]:
        """
        Runs health checks for all registered worker dependencies.
        Returns a dict of worker_name -> status ("Ready" or "Missing {dep}")
        """
        log.info("Running preflight health checks...")
        
        cache = {}
        
        for worker_name, caps in self.registry.items():
            status = "Ready"
            missing = []
            
            for req in caps.requires:
                if req == "internet":
                    if "internet" not in cache:
                        cache["internet"] = self._check_internet()
                    if not cache["internet"]:
                        missing.append("Internet")
                
                elif req in ["godot", "blender"]:
                    if req not in cache:
                        cache[req] = self._check_binary(req, req)
                    if not cache[req]:
                        missing.append(req.capitalize())
            
            if missing:
                status = f"Missing {' & '.join(missing)}"
                log.warning("Worker '%s' health check failed: %s", worker_name, status)
            else:
                log.info("Worker '%s' is Ready.", worker_name)
                
            self.health_status[worker_name] = status
            
        return self.health_status
