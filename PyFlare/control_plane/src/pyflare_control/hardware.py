"""Conservative Linux hardware profiler using only the Python standard library."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .models import HardwareSnapshot


def _available_memory_mb(meminfo: Path = Path("/proc/meminfo")) -> int:
    try:
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def discover_applications() -> frozenset[str]:
    commands = {
        "blender": ("blender",),
        "git": ("git",),
        "dotnet": ("dotnet",),
        "unity": ("unity-editor", "Unity"),
    }
    installed = {
        application
        for application, alternatives in commands.items()
        if any(shutil.which(command) for command in alternatives)
    }
    return frozenset(installed)


def capture_snapshot(
    *,
    online: bool,
    foreground_application: str | None = None,
    vram_available_mb: int | None = None,
    root_path: Path = Path("/"),
) -> HardwareSnapshot:
    try:
        disk_available_mb = shutil.disk_usage(root_path).free // (1024 * 1024)
    except OSError:
        disk_available_mb = 0

    try:
        load_1m = os.getloadavg()[0]
        threads = os.cpu_count() or 1
        cpu_available = max(0.0, min(100.0, 100.0 * (1.0 - load_1m / threads)))
    except (AttributeError, OSError):
        threads = os.cpu_count() or 1
        cpu_available = 50.0

    return HardwareSnapshot(
        captured_at=datetime.now(UTC).isoformat(),
        cpu_threads=threads,
        cpu_available_percent=cpu_available,
        ram_available_mb=_available_memory_mb(),
        vram_available_mb=vram_available_mb,
        disk_available_mb=disk_available_mb,
        online=online,
        installed_applications=discover_applications(),
        thermal_state="unknown",
        foreground_application=foreground_application,
    )
