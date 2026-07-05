from __future__ import annotations
import threading
import time
import os
import shutil
import psutil
from typing import Any, Callable, Dict, List, Optional
from ..logging_setup import get_logger
from ..db import Database

log = get_logger("background_scheduler")

class BackgroundScheduler:
    """Runs autonomous utility jobs while Jarvis is idle without impacting active user operations."""
    
    def __init__(self, db: Database, event_bus: Optional[Any] = None) -> None:
        self.db = db
        self.event_bus = event_bus
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._jobs: Dict[str, Callable[[], None]] = {}
        self._setup_default_jobs()
        
    def _setup_default_jobs(self) -> None:
        self.register_job("memory_consolidation", self._job_memory_consolidation)
        self.register_job("cache_cleanup", self._job_cache_cleanup)
        self.register_job("benchmark_providers", self._job_benchmark_providers)
        self.register_job("detect_regressions", self._job_detect_regressions)
        self.register_job("optimize_databases", self._job_optimize_databases)
        self.register_job("compress_logs", self._job_compress_logs)
        self.register_job("update_worker_scores", self._job_update_worker_scores)
        self.register_job("health_monitoring", self._job_health_monitoring)
 
    def register_job(self, name: str, callback: Callable[[], None]) -> None:
        with self._lock:
            self._jobs[name] = callback
            
    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, name="BackgroundScheduler", daemon=True)
            self._thread.start()
            log.info("Background scheduler started.")
            
    def stop(self) -> None:
        with self._lock:
            self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            log.info("Background scheduler stopped.")
 
    def _is_jarvis_idle(self) -> bool:
        # Check if there are active/running jobs in the database
        try:
            row = self.db.query_one("SELECT COUNT(*) AS c FROM jobs WHERE status = 'running'")
            active_jobs = int(row["c"]) if row else 0
            if active_jobs > 0:
                return False
        except Exception:
            pass
            
        # Check task queue table if it exists
        try:
            row = self.db.query_one("SELECT COUNT(*) AS c FROM task_queue WHERE status = 'running'")
            active_tasks = int(row["c"]) if row else 0
            if active_tasks > 0:
                return False
        except Exception:
            pass
            
        return True
 
    def _loop(self) -> None:
        while True:
            # Check flag thread-safely or stop event
            with self._lock:
                if not self._running:
                    break
            if self._stop_event.is_set():
                break
                    
            if self._is_jarvis_idle():
                # Perform jobs sequentially with gaps
                for name, job_func in list(self._jobs.items()):
                    with self._lock:
                        if not self._running:
                            break
                    if self._stop_event.is_set():
                        break
                    if not self._is_jarvis_idle():
                        log.info("User job started. Suspending background scheduler run.")
                        break
                        
                    try:
                        log.debug(f"Running background job: {name}")
                        job_func()
                        if self.event_bus:
                            self.event_bus.publish("scheduler_job_completed", {"job_name": name})
                    except Exception as e:
                        log.error(f"Error running background job {name}: {e}")
                        
                    # sleep between background jobs to prevent CPU spikes
                    if self._stop_event.wait(0.5):
                        break
            else:
                # Sleep if busy
                if self._stop_event.wait(1.0):
                    break
                
            if self._stop_event.wait(2.0):
                break

    # --- Job implementations --------------------------------------------------
    def _job_memory_consolidation(self) -> None:
        # Decay memory entries slightly
        self.db.execute("UPDATE memory SET created_at = created_at - 1.0 LIMIT 10")

    def _job_cache_cleanup(self) -> None:
        # Clean up stale/old embedding caches (e.g. older than 30 days)
        cutoff = time.time() - (30 * 24 * 3600)
        self.db.execute("DELETE FROM embeddings_cache WHERE created_at < ?", (cutoff,))

    def _job_benchmark_providers(self) -> None:
        # Simulated check or sync with BenchmarkEngine
        pass

    def _job_detect_regressions(self) -> None:
        # Check historical latencies or error rates
        pass

    def _job_optimize_databases(self) -> None:
        # Vacuum or clean up SQLite tables
        try:
            self.db.execute("PRAGMA optimize;")
        except Exception:
            pass

    def _job_compress_logs(self) -> None:
        # Compress log files or truncate job_events older than 7 days
        cutoff = time.time() - (7 * 24 * 3600)
        self.db.execute("DELETE FROM job_events WHERE created_at < ?", (cutoff,))

    def _job_update_worker_scores(self) -> None:
        # Refresh worker scoring structures
        pass

    def _job_health_monitoring(self) -> None:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        if self.event_bus:
            self.event_bus.publish("system_health", {"cpu_percent": cpu, "memory_percent": mem})
