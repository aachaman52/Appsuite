"""Pytest configuration and shared fixtures for PyFlare test suite."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator
import pytest

from pyflare.core.config import AppConfig
from pyflare.core.db import Database
from pyflare.providers.provider_manager import ProviderManager
from pyflare.core.token_banker import TokenBanker
from pyflare.core.hardware_manager import HardwareManager
from pyflare.memory.semantic_memory import SemanticMemory
from pyflare.core.jarvis_brain import JarvisBrain


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, tmp_path: Path):
    """Ensure safe isolated environment for all tests."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYFLARE_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("PYFLARE_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("PYFLARE_ALLOW_EXTERNAL_BIND", "false")
    monkeypatch.setenv("PYFLARE_FTP_ENABLED", "false")


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Provide a fresh SQLite database instance in temporary directory."""
    db_path = tmp_path / "test_pyflare.db"
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def test_config(tmp_path: Path) -> AppConfig:
    """Provide a test AppConfig instance."""
    raw = {
        "system": {"max_workers": 2, "thread_pool_size": 4, "cache_size_mb": 128},
        "limits": {"max_assets": 5, "gpu_vram_limit_mb": 2048, "ram_limit_mb": 4096},
        "timeouts": {"godot_headless_sec": 30, "blender_sec": 30, "http_request_sec": 10},
        "retries": {"worker_failure_limit": 2, "repair_retry_count": 2},
        "validation": {"score_threshold": 0.8},
        "server": {"host": "127.0.0.1", "port": 8000, "allow_external_bind": False},
        "log_dir": str(tmp_path / "logs"),
        "cache_dir": str(tmp_path / "cache"),
        "output_dir": str(tmp_path / "output"),
        "assets_dir": str(tmp_path / "assets"),
        "database_path": str(tmp_path / "db.sqlite"),
        "workers": {
            "godot": {"binary": "godot"},
            "blender": {"binary": "blender"},
            "deploy": {"ftp_enabled": False},
        },
    }
    cfg = AppConfig(raw=raw, providers=[], templates=[])
    cfg.ensure_dirs()
    return cfg


@pytest.fixture
def memory_and_brain(temp_db: Database, tmp_path: Path):
    """Provide pre-wired SemanticMemory and JarvisBrain."""
    provider_mgr = ProviderManager([])
    token_banker = TokenBanker({})
    hardware_mgr = HardwareManager({}, str(tmp_path))
    memory = SemanticMemory(temp_db, provider_mgr)
    brain = JarvisBrain(memory, provider_mgr, token_banker, hardware_mgr, templates=None)
    return memory, brain
