"""Configuration loader for AppSuite.

Loads JSON configuration files and resolves paths relative to the project root.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class AppConfig:
    raw: Dict[str, Any]
    providers: List[Dict[str, Any]] = field(default_factory=list)
    templates: List[Dict[str, Any]] = field(default_factory=list)

    # --- convenience accessors -------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def abs_path(self, key: str) -> Path:
        """Resolve a path-like config value against the project root."""
        value = self.raw[key]
        p = Path(value)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    @property
    def scheduler(self) -> Dict[str, Any]:
        return self.raw.get("scheduler", {})

    @property
    def retries(self) -> Dict[str, Any]:
        return self.raw.get("retries", {})

    @property
    def workers(self) -> Dict[str, Any]:
        return self.raw.get("workers", {})

    def ensure_dirs(self) -> None:
        for key in ("log_dir", "cache_dir", "output_dir", "assets_dir"):
            self.abs_path(key).mkdir(parents=True, exist_ok=True)
        self.abs_path("database_path").parent.mkdir(parents=True, exist_ok=True)


_cached: AppConfig | None = None


def load_config(reload: bool = False) -> AppConfig:
    global _cached
    if _cached is not None and not reload:
        return _cached
    base = _read_json(CONFIG_DIR / "config.json")
    providers = _read_json(CONFIG_DIR / "providers.json").get("providers", [])
    templates = _read_json(CONFIG_DIR / "templates.json").get("templates", [])
    cfg = AppConfig(raw=base, providers=providers, templates=templates)
    cfg.ensure_dirs()
    _cached = cfg
    return cfg