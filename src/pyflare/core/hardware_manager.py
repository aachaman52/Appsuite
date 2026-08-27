"""Hardware Manager - monitors CPU, RAM, Disk, GPU, and provides hardware profiling."""
from __future__ import annotations

import os
import platform
import shutil
import sys
import time
from typing import Any, Dict, Optional

from .logging_setup import get_logger

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

log = get_logger("hardware_manager")


class HardwareManager:
    def __init__(self, config: Dict[str, Any], output_dir: str = "."):
        self.config = config or {}
        self.output_dir = output_dir or "."
        self.start_time = time.time()
        self._last_net = None
        self._last_net_time = 0.0

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    def _gpu_stats(self) -> Dict[str, Any]:
        """Fetch GPU stats using nvidia-smi if available."""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, check=True, timeout=2.0
            )
            lines = result.stdout.strip().split('\n')
            if lines:
                parts = lines[0].split(',')
                if len(parts) >= 3:
                    total = float(parts[1].strip())
                    used = float(parts[2].strip())
                    free = float(parts[3].strip()) if len(parts) >= 4 else max(0.0, total - used)
                    return {
                        "available": True,
                        "name": parts[0].strip(),
                        "vram_total": total,
                        "vram_used": used,
                        "vram_free": free,
                    }
        except Exception:
            pass
        return {"available": False, "name": None, "vram_total": 0.0, "vram_used": 0.0, "vram_free": 0.0}

    def resources(self) -> Dict[str, Any]:
        cpu = ram = None
        ram_detail: Dict[str, Any] = {"total_mb": 8192.0, "used_mb": 4096.0, "available_mb": 4096.0}
        net: Dict[str, Any] = {}
        if _HAS_PSUTIL:
            try:
                cpu = psutil.cpu_percent(interval=None)
                vm = psutil.virtual_memory()
                ram = vm.percent
                ram_detail = {
                    "total_mb": round(vm.total / (1024 * 1024), 1),
                    "used_mb": round(vm.used / (1024 * 1024), 1),
                    "available_mb": round(vm.available / (1024 * 1024), 1),
                }
                counters = psutil.net_io_counters()
                now = time.time()
                if self._last_net is not None:
                    dt = max(now - self._last_net_time, 1e-6)
                    net = {
                        "sent_kbps": (counters.bytes_sent - self._last_net.bytes_sent) / dt / 1024,
                        "recv_kbps": (counters.bytes_recv - self._last_net.bytes_recv) / dt / 1024,
                    }
                self._last_net = counters
                self._last_net_time = now
            except Exception:
                pass

        try:
            target_dir = self.output_dir if os.path.exists(self.output_dir) else "."
            usage = shutil.disk_usage(target_dir)
            disk = {
                "total_gb": round(usage.total / 1e9, 2),
                "free_gb": round(usage.free / 1e9, 2),
                "used_percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            disk = {"total_gb": 100.0, "free_gb": 50.0, "used_percent": 50.0}

        return {
            "psutil_available": _HAS_PSUTIL,
            "cpu_percent": cpu if cpu is not None else 10.0,
            "ram_percent": ram if ram is not None else 50.0,
            "ram": ram_detail,
            "disk": disk,
            "gpu": self._gpu_stats(),
            "network": net,
        }

    def get_hardware_profile(self) -> Any:
        """
        Generate a normalized HardwareProfile model instance.
        Lazy imports router.models to avoid circular imports.
        """
        from pyflare.router.models import HardwareProfile, HardwareTier

        res = self.resources()
        gpu = res.get("gpu", {})
        ram = res.get("ram", {})
        disk = res.get("disk", {})

        logical_cores = os.cpu_count() or 1
        physical_cores = logical_cores
        if _HAS_PSUTIL:
            try:
                physical_cores = psutil.cpu_count(logical=False) or logical_cores
            except Exception:
                pass

        ram_total = float(ram.get("total_mb", 8192.0))
        ram_avail = float(ram.get("available_mb", ram_total * 0.5))
        vram_total = float(gpu.get("vram_total", 0.0))
        vram_avail = float(gpu.get("vram_free", 0.0))

        # Check binaries
        installed = {
            "blender": shutil.which("blender") is not None,
            "godot": shutil.which("godot") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "git": shutil.which("git") is not None,
            "python": True,
        }

        # Determine Tier
        if ram_total >= 16000 and vram_total >= 6000 and logical_cores >= 8:
            tier = HardwareTier.HIGH
        elif ram_total >= 7500 and (vram_total >= 2000 or logical_cores >= 4):
            tier = HardwareTier.MID
        else:
            tier = HardwareTier.WEAK

        pressure = {
            "cpu_percent": float(res.get("cpu_percent", 10.0)),
            "ram_percent": float(res.get("ram_percent", 50.0)),
            "disk_percent": float(disk.get("used_percent", 50.0)),
        }

        return HardwareProfile(
            cpu_cores_logical=logical_cores,
            cpu_cores_physical=physical_cores,
            ram_total_mb=ram_total,
            ram_available_mb=ram_avail,
            gpu_name=gpu.get("name"),
            vram_total_mb=vram_total,
            vram_available_mb=vram_avail,
            disk_available_gb=float(disk.get("free_gb", 20.0)),
            os_name=sys.platform,
            hardware_tier=tier,
            installed_binaries=installed,
            resource_pressure=pressure,
        )

    def can_worker_run(self, worker_name: str) -> bool:
        """
        Check if the specific worker can run based on current hardware stats.
        Blender and Godot are considered heavy workers and require more RAM.
        """
        res = self.resources()
        ram = res.get("ram_percent")

        if ram is None:
            return True

        if worker_name in ("blender", "godot"):
            if ram > 85.0:
                log.warning("HardwareManager: Pausing heavy worker '%s' (RAM at %.1f%% > 85.0%%)", worker_name, ram)
                return False

        if ram > 95.0:
            log.warning("HardwareManager: System critically low on RAM (%.1f%%). Pausing %s", ram, worker_name)
            return False

        return True
