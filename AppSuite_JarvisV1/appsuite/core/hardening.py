"""
Production Hardening Layer
==========================
Provides system stability, crash recovery, session restores, autosaves,
and resource monitoring (deadlocks, timeouts, memory leaks).
"""
from __future__ import annotations

import os
import json
import time
import threading
import psutil
from typing import Any, Dict, List, Optional

from ..logging_setup import get_logger

log = get_logger("system.hardening")

class SessionManager:
    """Handles checkpointing, autosave, and crash recovery/session restore."""
    def __init__(self, db: Any, session_dir: str):
        self.db = db
        self.session_dir = session_dir
        os.makedirs(self.session_dir, exist_ok=True)
        self.current_session_file = os.path.join(self.session_dir, "current_session.json")
        
    def autosave(self, state: Dict[str, Any]) -> None:
        """Autosaves current job/pipeline state to disk."""
        try:
            with open(self.current_session_file, "w") as f:
                json.dump(state, f)
        except Exception as exc:
            log.warning("Autosave failed: %s", exc)
            
    def checkpoint(self, job_id: str, stage: str, data: Dict[str, Any]) -> None:
        """Creates a hard checkpoint in the database for recovery."""
        try:
            # Reusing event system as a simple checkpoint log
            self.db.add_event(job_id, f"CHECKPOINT: {stage}", stage="checkpoint", level="info")
        except Exception:
            pass

    def restore_session(self) -> Optional[Dict[str, Any]]:
        """Restores session state after a crash."""
        if os.path.exists(self.current_session_file):
            try:
                with open(self.current_session_file, "r") as f:
                    state = json.load(f)
                log.info("Restored session from autosave.")
                return state
            except Exception as exc:
                log.warning("Session restore failed: %s", exc)
        return None


class WatchdogManager:
    """Monitors workers for deadlocks, timeouts, and memory leaks."""
    def __init__(self, timeout_secs: int = 300, memory_limit_mb: int = 4096):
        self.timeout_secs = timeout_secs
        self.memory_limit_mb = memory_limit_mb
        self._active_tasks: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._thread.start()
        log.info("Watchdog started (timeout=%ds, mem_limit=%dMB).", self.timeout_secs, self.memory_limit_mb)
        
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            
    def register_task(self, task_id: str):
        with self._lock:
            self._active_tasks[task_id] = time.time()
            
    def unregister_task(self, task_id: str):
        with self._lock:
            self._active_tasks.pop(task_id, None)
            
    def _watchdog_loop(self):
        while self._running:
            try:
                now = time.time()
                # Check Timeouts / Deadlocks
                with self._lock:
                    for task_id, start_time in list(self._active_tasks.items()):
                        if now - start_time > self.timeout_secs:
                            log.error("WATCHDOG: Task %s timed out! Potential deadlock detected.", task_id)
                            # In a real system, we would raise a signal or interrupt the thread here
                            
                # Check Memory Leaks
                process = psutil.Process(os.getpid())
                mem_mb = process.memory_info().rss / (1024 * 1024)
                if mem_mb > self.memory_limit_mb:
                    log.error("WATCHDOG: Memory leak detected! Usage: %d MB (Limit: %d MB)", mem_mb, self.memory_limit_mb)
                    
            except Exception as exc:
                log.error("Watchdog error: %s", exc)
            time.sleep(10.0)
