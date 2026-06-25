"""Hardware Manager - monitors CPU, RAM, Disk, and controls worker execution."""
from __future__ import annotations

import shutil
import time
from typing import Any, Dict

from ..logging_setup import get_logger

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

log = get_logger("hardware_manager")

class HardwareManager:
    def __init__(self, config: Dict[str, Any], output_dir: str):
        self.config = config
        self.output_dir = output_dir
        self.start_time = time.time()
        self._last_net = None
        self._last_net_time = 0.0

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    def _gpu_stats(self) -> Dict[str, Any]:
        """Simple mock for GPU stats (same as previous implementation)."""
        return {"available": False, "name": None, "vram_total": 0, "vram_used": 0}

    def resources(self) -> Dict[str, Any]:
        cpu = ram = None
        ram_detail: Dict[str, Any] = {}
        net: Dict[str, Any] = {}
        if _HAS_PSUTIL:
            cpu = psutil.cpu_percent(interval=None)
            vm  = psutil.virtual_memory()
            ram = vm.percent
            ram_detail = {"total_mb": vm.total // (1024 * 1024),
                          "used_mb":  vm.used  // (1024 * 1024)}
            try:
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
                net = {}
        usage = shutil.disk_usage(self.output_dir)
        disk  = {
            "total_gb":    round(usage.total / 1e9, 2),
            "free_gb":     round(usage.free  / 1e9, 2),
            "used_percent": round(usage.used / usage.total * 100, 1),
        }
        return {
            "psutil_available": _HAS_PSUTIL,
            "cpu_percent":  cpu,
            "ram_percent":  ram,
            "ram":  ram_detail,
            "disk": disk,
            "gpu":  self._gpu_stats(),
            "network": net,
        }

    def can_worker_run(self, worker_name: str) -> bool:
        """
        Check if the specific worker can run based on current hardware stats.
        Blender and Godot are considered heavy workers and require more RAM.
        """
        res = self.resources()
        cpu = res.get("cpu_percent")
        ram = res.get("ram_percent")
        
        if ram is None:
            return True # Cannot monitor, assume true
            
        # Heavy workers need more RAM headroom
        if worker_name in ("blender", "godot"):
            if ram > 85.0:
                log.warning("HardwareManager: Pausing heavy worker '%s' (RAM at %.1f%% > 85.0%%)", worker_name, ram)
                return False
                
        # General check
        if ram > 95.0:
            log.warning("HardwareManager: System critically low on RAM (%.1f%%). Pausing %s", ram, worker_name)
            return False
            
        return True
