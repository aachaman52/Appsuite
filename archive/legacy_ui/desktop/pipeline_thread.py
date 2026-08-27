"""Pipeline QThread — runs AppSuite pipeline jobs and emits Qt signals for each event.

The entire appsuite backend runs in-process, so no HTTP server is required.
Signals fire on every stage transition, log line, and asset discovery so the
UI can update in real-time without polling.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal


# ─── Signal bundle ────────────────────────────────────────────────────────────

class PipelineSignals(QObject):
    """All signals emitted during a pipeline run."""

    # Lifecycle
    started = Signal(str)             # job_id
    finished = Signal(str, dict)      # job_id, summary
    failed = Signal(str, str)         # job_id, error_message

    # Stage
    stage_started = Signal(str, str)  # job_id, stage_name
    stage_done = Signal(str, str, float, dict)  # job_id, stage, duration_s, result
    progress = Signal(str, float)     # job_id, 0.0-1.0

    # Logging
    log_line = Signal(str, str, str)  # job_id, level, message

    # Assets
    asset_found = Signal(str, dict)   # job_id, asset_dict

    # Resources
    resource_update = Signal(dict)    # {cpu, ram, disk}


# ─── Instrumented pipeline wrapper ────────────────────────────────────────────

class InstrumentedPipeline:
    """
    Wraps the real Pipeline to intercept stage transitions and emit signals.
    Replaces the vanilla execute() call with an instrumented version.
    """

    def __init__(self, real_pipeline, signals: PipelineSignals):
        self._pipeline = real_pipeline
        self._sig = signals

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = job["id"]
        self._sig.started.emit(job_id)

        # Patch db.add_event to forward log lines to the UI
        orig_add_event = self._pipeline.db.add_event

        def intercepted_add_event(jid, message, stage="", level="info"):
            orig_add_event(jid, message, stage=stage, level=level)
            if jid == job_id:
                self._sig.log_line.emit(job_id, level, f"[{stage or '—'}] {message}")

        self._pipeline.db.add_event = intercepted_add_event

        total_stages = len(self._pipeline.stages)

        # Patch each worker's run() to emit stage signals
        original_runs = {}
        for i, (stage, worker_key) in enumerate(self._pipeline.stages):
            worker = self._pipeline.workers.get(worker_key)
            if worker is None:
                continue
            original_runs[worker_key] = worker.run

            def make_run(orig_run, s=stage, k=worker_key, idx=i):
                def patched_run(job_arg, state_arg):
                    self._sig.stage_started.emit(job_id, s)
                    self._sig.progress.emit(job_id, idx / total_stages)
                    t0 = time.monotonic()
                    result = orig_run(job_arg, state_arg)
                    duration = time.monotonic() - t0
                    self._sig.stage_done.emit(job_id, s, duration, result)
                    # Emit asset signals for newly fetched assets
                    for asset in state_arg.get("assets", []):
                        self._sig.asset_found.emit(job_id, dict(asset))
                    return result
                return patched_run

            worker.run = make_run(original_runs[worker_key])

        try:
            summary = self._pipeline.execute(job)
            self._sig.progress.emit(job_id, 1.0)
            self._sig.finished.emit(job_id, summary)
            return summary
        except Exception as exc:
            self._sig.failed.emit(job_id, str(exc))
            raise
        finally:
            # Restore original methods
            self._pipeline.db.add_event = orig_add_event
            for worker_key, orig in original_runs.items():
                worker = self._pipeline.workers.get(worker_key)
                if worker:
                    worker.run = orig


# ─── Pipeline QThread ─────────────────────────────────────────────────────────

class PipelineThread(QThread):
    """
    Runs a single pipeline job in a background thread.
    All feedback goes through PipelineSignals.
    """

    def __init__(
        self,
        job_id: str,
        job: Dict[str, Any],
        pipeline,
        signals: PipelineSignals,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.job_id = job_id
        self.job = job
        self._instrumented = InstrumentedPipeline(pipeline, signals)
        self.signals = signals

    def run(self):
        try:
            self._instrumented.execute(self.job)
        except Exception:
            # Error already emitted by InstrumentedPipeline
            pass


# ─── Resource polling thread ──────────────────────────────────────────────────

class ResourceThread(QThread):
    """
    Polls CPU / RAM / Disk every `interval_ms` milliseconds.
    Emits resource_update signal to update the resource monitor widget.
    """

    update = Signal(dict)

    def __init__(self, interval_ms: int = 2500, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._interval = interval_ms
        self._stop = False

    def run(self):
        try:
            import psutil  # type: ignore
            has_psutil = True
        except ImportError:
            has_psutil = False

        while not self._stop:
            if has_psutil:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    ram = psutil.virtual_memory()
                    disk = psutil.disk_usage(".")
                    self.update.emit({
                        "cpu_pct": cpu,
                        "ram_pct": ram.percent,
                        "ram_used_mb": ram.used // (1024 * 1024),
                        "ram_total_mb": ram.total // (1024 * 1024),
                        "disk_free_gb": disk.free / (1024 ** 3),
                        "disk_total_gb": disk.total / (1024 ** 3),
                        "disk_pct": disk.percent,
                    })
                except Exception:
                    pass
            else:
                self.update.emit({
                    "cpu_pct": None, "ram_pct": None,
                    "ram_used_mb": None, "ram_total_mb": None,
                    "disk_free_gb": None, "disk_total_gb": None, "disk_pct": None,
                })
            self.msleep(self._interval)

    def stop(self):
        self._stop = True
