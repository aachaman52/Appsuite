"""Hardware detection and profiling for PyFlare AI development environment.

Cross-platform hardware detection (Linux & Windows) using Python standard library,
with accelerator detection, storage checking, and inference runtime discovery.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import HardwareSnapshot


@dataclass(frozen=True, slots=True)
class HardwareReport:
    cpu_architecture: str
    cpu_cores: int
    cpu_threads: int
    ram_total_mb: int
    ram_available_mb: int
    gpu_name: str | None
    gpu_vram_mb: int | None
    accelerator_type: str | None
    storage_total_mb: int
    storage_available_mb: int
    supported_runtimes: tuple[str, ...]
    installed_applications: frozenset[str]
    online: bool
    platform_system: str

    def to_snapshot(
        self,
        *,
        foreground_application: str | None = None,
        thermal_state: str = "nominal",
    ) -> HardwareSnapshot:
        return HardwareSnapshot(
            captured_at=datetime.now(UTC).isoformat(),
            cpu_threads=self.cpu_threads,
            cpu_available_percent=50.0,
            ram_available_mb=self.ram_available_mb,
            vram_available_mb=self.gpu_vram_mb,
            disk_available_mb=self.storage_available_mb,
            online=self.online,
            installed_applications=self.installed_applications,
            thermal_state=thermal_state,
            foreground_application=foreground_application,
        )


def _available_memory_mb(meminfo: Path = Path("/proc/meminfo")) -> int:
    """Read available RAM in MB on Linux, Windows, or POSIX fallback."""
    # 1. Windows ctypes API
    if platform.system() == "Windows":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullAvailPhys // (1024 * 1024))
        except Exception:
            pass

    # 2. Linux /proc/meminfo
    try:
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass

    # 3. Fallback heuristic
    return 4096


def _total_memory_mb(meminfo: Path = Path("/proc/meminfo")) -> int:
    """Read total RAM in MB."""
    if platform.system() == "Windows":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys // (1024 * 1024))
        except Exception:
            pass

    try:
        if meminfo.exists():
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass

    return 8192


def detect_gpu() -> tuple[str | None, int | None, str | None]:
    """Detect GPU vendor, name, VRAM (MB), and accelerator kind."""
    # 1. NVIDIA via nvidia-smi
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            res = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = line.split(",")
                gpu_name = parts[0].strip()
                vram_mb = int(parts[1].strip()) if len(parts) > 1 else None
                return gpu_name, vram_mb, "cuda"
        except (subprocess.SubprocessError, ValueError, OSError):
            pass

    # 2. Apple Metal / macOS
    if platform.system() == "Darwin":
        return "Apple Silicon GPU", None, "metal"

    # 3. No dedicated accelerator detected
    return None, None, None


def discover_supported_runtimes() -> tuple[str, ...]:
    """Identify available local AI inference runtimes."""
    runtimes: list[str] = []

    # Command line binaries
    if shutil.which("ollama"):
        runtimes.append("ollama")
    if shutil.which("llama-cli") or shutil.which("llama-server"):
        runtimes.append("llama.cpp")

    # Python packages
    try:
        import onnxruntime  # noqa: F401
        runtimes.append("onnxruntime")
    except ImportError:
        pass

    try:
        import torch  # noqa: F401
        runtimes.append("pytorch")
    except ImportError:
        pass

    # PyFlare builtin deterministic rule engine is always available
    runtimes.append("deterministic-local")
    return tuple(sorted(runtimes))


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


def detect_hardware(*, online: bool = True, target_path: Path | None = None) -> HardwareReport:
    """Capture a comprehensive structured hardware report."""
    root_path = target_path or Path.cwd().anchor or Path("/")
    try:
        usage = shutil.disk_usage(root_path)
        storage_total_mb = int(usage.total // (1024 * 1024))
        storage_avail_mb = int(usage.free // (1024 * 1024))
    except OSError:
        storage_total_mb = 0
        storage_avail_mb = 0

    threads = os.cpu_count() or 1
    cores = max(1, threads // 2) if threads > 1 else 1

    gpu_name, gpu_vram_mb, accelerator = detect_gpu()

    return HardwareReport(
        cpu_architecture=platform.machine() or "unknown",
        cpu_cores=cores,
        cpu_threads=threads,
        ram_total_mb=_total_memory_mb(),
        ram_available_mb=_available_memory_mb(),
        gpu_name=gpu_name,
        gpu_vram_mb=gpu_vram_mb,
        accelerator_type=accelerator,
        storage_total_mb=storage_total_mb,
        storage_available_mb=storage_avail_mb,
        supported_runtimes=discover_supported_runtimes(),
        installed_applications=discover_applications(),
        online=online,
        platform_system=platform.system(),
    )


def capture_snapshot(
    *,
    online: bool,
    foreground_application: str | None = None,
    vram_available_mb: int | None = None,
    root_path: Path | None = None,
) -> HardwareSnapshot:
    """Backward-compatible snapshot capture function."""
    check_path = root_path or Path.cwd().anchor or Path("/")
    try:
        disk_available_mb = shutil.disk_usage(check_path).free // (1024 * 1024)
    except OSError:
        disk_available_mb = 0

    try:
        load_1m = os.getloadavg()[0]
        threads = os.cpu_count() or 1
        cpu_available = max(0.0, min(100.0, 100.0 * (1.0 - load_1m / threads)))
    except (AttributeError, OSError):
        threads = os.cpu_count() or 1
        cpu_available = 50.0

    gpu_name, detected_vram, _ = detect_gpu()
    effective_vram = vram_available_mb if vram_available_mb is not None else detected_vram

    return HardwareSnapshot(
        captured_at=datetime.now(UTC).isoformat(),
        cpu_threads=threads,
        cpu_available_percent=cpu_available,
        ram_available_mb=_available_memory_mb(),
        vram_available_mb=effective_vram,
        disk_available_mb=disk_available_mb,
        online=online,
        installed_applications=discover_applications(),
        thermal_state="nominal",
        foreground_application=foreground_application,
    )
