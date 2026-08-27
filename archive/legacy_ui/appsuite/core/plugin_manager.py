"""Plugin architecture - discovers and loads plugins from a directory.

A plugin is a Python module exposing `register(context: dict) -> dict`.
It may contribute extra hooks (e.g. post-processing callbacks).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

from ..logging_setup import get_logger

log = get_logger("plugin_manager")


class PluginManager:
    def __init__(self, directory: Path, enabled: bool = True):
        self.directory = directory
        self.enabled = enabled
        self.plugins: List[Dict[str, Any]] = []
        
        # Plugin registries
        self.registered_workers: Dict[str, Any] = {}
        self.registered_adapters: List[Any] = []
        self.registered_agents: List[Any] = []

    def load(self, context: Dict[str, Any]) -> None:
        if not self.enabled or not self.directory.exists():
            return
        for file in sorted(self.directory.glob("*.py")):
            if file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(f"plugin_{file.stem}", file)
                module = importlib.util.module_from_spec(spec)  # type: ignore
                spec.loader.exec_module(module)  # type: ignore
                if hasattr(module, "register"):
                    info = module.register(context) or {}
                    info.setdefault("name", file.stem)
                    info["module"] = module
                    self.plugins.append(info)
                    
                    # Process registrations
                    if "workers" in info:
                        self.registered_workers.update(info["workers"])
                    if "adapters" in info:
                        self.registered_adapters.extend(info["adapters"])
                    if "agents" in info:
                        self.registered_agents.extend(info["agents"])
                        
                    log.info("Loaded plugin: %s (Workers: %d, Adapters: %d, Agents: %d)", 
                             info["name"], len(info.get("workers", {})), 
                             len(info.get("adapters", [])), len(info.get("agents", [])))
            except Exception as exc:  # pragma: no cover
                log.error("Failed to load plugin %s: %s", file.name, exc)


    def run_hook(self, hook: str, *args: Any, **kwargs: Any) -> List[Any]:
        results = []
        for p in self.plugins:
            fn = getattr(p["module"], hook, None)
            if callable(fn):
                try:
                    results.append(fn(*args, **kwargs))
                except Exception as exc:  # pragma: no cover
                    log.error("Plugin %s hook %s failed: %s", p["name"], hook, exc)
        return results

    def list(self) -> List[str]:
        return [p["name"] for p in self.plugins]