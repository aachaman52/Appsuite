import os
import json
import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .logging_setup import get_structured_logger

if TYPE_CHECKING:
    from .runtime_engine import RuntimeContext

log = get_structured_logger("crash_manager")

class CrashManager:
    def __init__(self, config: Any, event_bus: Any):
        self.config = config
        self.event_bus = event_bus
        self.crash_dir = Path("crash_reports")
        self.crash_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_memory_snapshot(self) -> dict:
        try:
            import psutil
            process = psutil.Process()
            return {
                "rss_mb": process.memory_info().rss / (1024 * 1024),
                "vms_mb": process.memory_info().vms / (1024 * 1024),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "threads": process.num_threads()
            }
        except ImportError:
            return {"error": "psutil not installed"}

    def handle_crash(self, ctx: Any, dag: Any, exception: Exception):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_dir = self.crash_dir / timestamp
        report_dir.mkdir(parents=True, exist_ok=True)
        
        log.critical("Pipeline crashed! Saving crash report to %s", report_dir)

        # 1. Stack trace
        with open(report_dir / "traceback.txt", "w", encoding="utf-8") as f:
            traceback.print_exception(type(exception), exception, exception.__traceback__, file=f)
            
        # 2. RuntimeContext
        ctx_data = {
            "job_id": getattr(ctx, "job_id", ""),
            "current_worker": getattr(ctx, "current_worker", ""),
            "workers_finished": getattr(ctx, "workers_finished", []),
            "workers_remaining": getattr(ctx, "workers_remaining", []),
            "retries": getattr(ctx, "retries", {}),
            "assets": getattr(ctx, "assets", {}),
            "shared_objects": getattr(ctx, "shared_objects", {}),
            "current_errors": getattr(ctx, "current_errors", [])
        }
        with open(report_dir / "runtime_context.json", "w", encoding="utf-8") as f:
            json.dump(ctx_data, f, indent=4)
            
        # 3. Memory Snapshot
        with open(report_dir / "memory_snapshot.json", "w", encoding="utf-8") as f:
            json.dump(self._get_memory_snapshot(), f, indent=4)
            
        # 4. Config Snapshot
        config_raw = getattr(self.config, "raw", {}) if self.config else {}
        with open(report_dir / "config_snapshot.json", "w", encoding="utf-8") as f:
            json.dump(config_raw, f, indent=4)
            
        # 5. DAG Snapshot
        dag_data = {
            "sequence": getattr(dag, "sequence", []),
            "history": getattr(dag, "history", [])
        }
        with open(report_dir / "dag_snapshot.json", "w", encoding="utf-8") as f:
            json.dump(dag_data, f, indent=4)

        return str(report_dir)

    def load_crash(self, report_dir: str) -> dict:
        """Loads a crash report to resume."""
        path = Path(report_dir)
        if not path.exists():
            raise FileNotFoundError(f"Crash report {report_dir} not found.")
            
        with open(path / "runtime_context.json", "r") as f:
            ctx_data = json.load(f)
            
        with open(path / "dag_snapshot.json", "r") as f:
            dag_data = json.load(f)
            
        return {
            "context": ctx_data,
            "dag": dag_data
        }
