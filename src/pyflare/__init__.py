"""
PyFlare — Autonomous AI Agent Orchestration and Development Platform.

Canonical package for PyFlare.
"""

__version__ = "1.0.0"
__product__ = "PyFlare"

# Re-export core classes for easy top-level access
from pyflare.core.jarvis import JarvisCore, Jarvis, PyFlareEngine
from pyflare.core.db import Database
from pyflare.core.config import get_config, AppConfig, AppConfig as PyFlareConfig, load_config
from pyflare.core.models import JobCreateRequest, JobResponse, JobEvent, AssetResponse, SystemStatus
from pyflare.core.logging_setup import get_logger, get_structured_logger

__all__ = [
    "__version__",
    "__product__",
    "JarvisCore",
    "Jarvis",
    "PyFlareEngine",
    "Database",
    "get_config",
    "load_config",
    "AppConfig",
    "PyFlareConfig",
    "JobCreateRequest",
    "JobResponse",
    "JobEvent",
    "AssetResponse",
    "SystemStatus",
    "get_logger",
    "get_structured_logger",
]
