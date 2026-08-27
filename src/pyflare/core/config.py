"""Configuration loader for PyFlare.

Loads YAML and JSON configuration files, checks environment overrides,
and resolves paths relative to the workspace/project root.
"""
from __future__ import annotations

import json
import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_project_root() -> Path:
    """Detect project root directory by searching for markers like pyproject.toml or src/."""
    current = Path(__file__).resolve().parent
    for p in [current, current.parent, current.parent.parent, current.parent.parent.parent]:
        if (p / "pyproject.toml").exists() or (p / "config").exists():
            return p
    return Path.cwd()


PROJECT_ROOT = find_project_root()
CONFIG_DIR = Path(os.environ.get("PYFLARE_CONFIG_DIR", str(PROJECT_ROOT / "config")))


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


DEFAULT_RAW_CONFIG: Dict[str, Any] = {
    "system": {
        "max_workers": 4,
        "thread_pool_size": 8,
        "cache_size_mb": 1024,
    },
    "limits": {
        "max_assets": 10,
        "gpu_vram_limit_mb": 4096,
        "ram_limit_mb": 8192,
    },
    "timeouts": {
        "godot_headless_sec": 300,
        "blender_sec": 300,
        "http_request_sec": 60,
    },
    "retries": {
        "worker_failure_limit": 2,
        "repair_retry_count": 3,
    },
    "validation": {
        "score_threshold": 0.8,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
        "allow_external_bind": False,
    },
    "log_dir": "output/logs",
    "cache_dir": "output/cache",
    "output_dir": "output",
    "assets_dir": "output/assets",
    "database_path": "data/pyflare.db",
    "workers": {
        "godot": {"binary": "godot"},
        "blender": {"binary": "blender"},
        "deploy": {"ftp_enabled": False},
    },
}


@dataclass
class AppConfig:
    raw: Dict[str, Any]
    providers: List[Dict[str, Any]] = field(default_factory=list)
    templates: List[Dict[str, Any]] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def abs_path(self, key: str) -> Path:
        """Resolve a path-like config value against the project root."""
        value = self.raw.get(key, f"output/{key}")
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
            try:
                self.abs_path(key).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
        try:
            self.abs_path("database_path").parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


_cached: Optional[AppConfig] = None


def load_config(reload: bool = False) -> AppConfig:
    global _cached
    if _cached is not None and not reload:
        return _cached

    base = DEFAULT_RAW_CONFIG.copy()
    
    yaml_config = CONFIG_DIR / "default_config.yaml"
    if yaml_config.exists():
        loaded_base = _read_yaml(yaml_config)
        for k, v in loaded_base.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v

    user_config_path = CONFIG_DIR / "user_config.yaml"
    if user_config_path.exists():
        user_cfg = _read_yaml(user_config_path)
        for k, v in user_cfg.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v

    providers_file = CONFIG_DIR / "providers.json"
    providers = _read_json(providers_file).get("providers", []) if providers_file.exists() else []

    templates_file = CONFIG_DIR / "templates.json"
    templates = _read_json(templates_file).get("templates", []) if templates_file.exists() else []

    cfg = AppConfig(raw=base, providers=providers, templates=templates)
    cfg.ensure_dirs()
    _cached = cfg
    return cfg


def get_config() -> AppConfig:
    return load_config()