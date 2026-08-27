"""Unit tests for PyFlare configuration loader."""
from pathlib import Path
import pytest

from pyflare.core.config import AppConfig, load_config, DEFAULT_RAW_CONFIG


@pytest.mark.unit
def test_load_default_config():
    """Verify default config loads with expected values."""
    cfg = load_config(reload=True)
    assert isinstance(cfg, AppConfig)
    assert "system" in cfg.raw
    assert cfg.raw["system"]["max_workers"] >= 1
    assert "server" in cfg.raw
    assert cfg.raw["server"]["host"] in ("127.0.0.1", "localhost")


@pytest.mark.unit
def test_abs_path_resolution(tmp_path: Path):
    """Verify relative path resolution against project root."""
    cfg = AppConfig(raw={"log_dir": "output/logs", "output_dir": "output"})
    resolved = cfg.abs_path("log_dir")
    assert isinstance(resolved, Path)
    assert "logs" in str(resolved)
