"""Supervisor - job management, worker orchestration, failure recovery, monitoring.

Runs a background scheduler loop that pulls queued jobs, checks resource
availability via Jarvis, dispatches them through the pipeline, retries on
failure, and records outcomes to memory.
Also acts as the active control layer inside the pipeline for self-healing.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Dict, Optional

from ..logging_setup import get_logger
from .state import WorkerResult, WorkerStatus

log = get_logger("supervisor")


class SupervisorAction(Enum):
    RETRY = "retry"
    CHANGE_PROVIDER = "change_provider"
    REPLAN = "replan"
    SKIP = "skip"
    ABORT = "abort"
    PROCEED = "proceed"


class Supervisor:
    def __init__(self, db, jarvis, pipeline, memory, scheduler_cfg, retries_cfg, brain=None,
                 jarvis_memory=None):
        self.db = db
        self.jarvis = jarvis
        self.pipeline = pipeline
        self.memory = memory
        self.scheduler_cfg = scheduler_cfg
        self.retries_cfg = retries_cfg
        self.brain = brain
        self.jarvis_memory = jarvis_memory  # Typed Jarvis Memory System
        
        self.max_concurrent = int(scheduler_cfg.get("max_concurrent_jobs", 2))
        self.poll = float(scheduler_cfg.get("poll_interval_seconds", 1.0))
        self._pool = ThreadPoolExecutor(max_workers=self.max_concurrent)
        self._active: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # State tracking for failure recovery within jobs
        self._failures: Dict[str, Dict[str, int]] = {}  # job_id -> {stage: fail_count}
        
        # recover any jobs left 'running' from a previous crash
        self._recover_orphans()

    # ------------------------------------------------------------------ pipeline control
    def handle_result(self, job_id: str, stage: str, result: WorkerResult) -> SupervisorAction:
        """
        Analyze WorkerStatus and failure reasons.
        Decide recovery actions and prevent infinite failures.
        """
        status = result.status
        reason = result.reason or str(result.data)
        
        log.info("Supervisor evaluating result: status=%s, reason=%r", status.name, reason)

        if status == WorkerStatus.SUCCESS:
            return SupervisorAction.PROCEED

        if status == WorkerStatus.NEED_ASSET:
            return SupervisorAction.PROCEED # Pipeline knows to route this to asset_search naturally

        # Track failure count
        if job_id not in self._failures:
            self._failures[job_id] = {}
        stage_fails = self._failures[job_id].get(stage, 0) + 1
        self._failures[job_id][stage] = stage_fails

        max_attempts = int(self.retries_cfg.get("max_attempts", 3))

        log.warning(
            "Supervisor: Stage %s returned %s (Failures: %d/%d). Reason: %s",
            stage, status.name, stage_fails, max_attempts, reason[:100]
        )

        if stage_fails >= max_attempts:
            log.error("Supervisor: Max failures reached for %s. Aborting.", stage)
            return SupervisorAction.ABORT

        if status == WorkerStatus.FAILED:
            # Fatal errors that cannot be retried
            if any(k in reason for k in ("GODOT_NOT_FOUND", "FILE_NOT_FOUND")):
                log.error("Supervisor: Non-recoverable error detected: %s. Aborting.", reason[:50])
                return SupervisorAction.ABORT
            
            # Simulated timeout for testing purposes
            if "simulated timeout" in reason.lower():
                log.info("Supervisor: Transient error detected, ordering RETRY")
                time.sleep(1.0)
                return SupervisorAction.RETRY

            # General failures
            return SupervisorAction.RETRY

        if status == WorkerStatus.NEED_RETRY:
            time.sleep(2.0 * stage_fails)
            return SupervisorAction.RETRY

        return SupervisorAction.ABORT

    # ------------------------------------------------------------------ public daemon
    def submit(self, prompt: str, template_id: Optional[str] = None) -> str:
        job_id = str(uuid.uuid4())
        self.db.create_job(job_id, prompt, template_id)
        self.db.add_event(job_id, "Job queued", stage="queue")
        log.info("Submitted job %s", job_id)
        return job_id

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="supervisor", daemon=True)
        self._thread.start()
        log.info("Supervisor loop started")

    def stop(self) -> None:
        self._stop.set()
        self._pool.shutdown(wait=True)
        if self._thread:
            self._thread.join(timeout=5.0)

    def status(self) -> Dict[str, Any]:
        rows = self.db.list_jobs(500)
        counts: Dict[str, int] = {}
        for r in rows:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        with self._lock:
            active = list(self._active.keys())
        return {"counts": counts, "active": active, "max_concurrent": self.max_concurrent}

    # ----------------------------------------------------------------- internal daemon
    def _recover_orphans(self) -> None:
        for job in self.db.list_jobs(1000):
            if job["status"] == "running":
                self.db.update_job(job["id"], status="queued", stage=None)
                self.db.add_event(job["id"], "Recovered orphaned running job -> requeued",
                                  stage="recovery", level="warn")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001
                log.error("Scheduler tick error: %s", exc)
            time.sleep(self.poll)

    def _tick(self) -> None:
        if self._stop.is_set():
            return
        with self._lock:
            if len(self._active) >= self.max_concurrent:
                return
        ok, reason = self.jarvis.can_schedule()
        if not ok:
            return
        job = self.db.next_queued_job()
        if not job:
            return
        
        # --- Consult Jarvis Memory before dispatching ---
        if self.jarvis_memory:
            try:
                mem_ctx = self.jarvis_memory.build_planning_context(job["prompt"])
                # Attach memory context to the job dict so pipeline can use it
                job["_memory_context"] = mem_ctx
            except Exception as exc:
                log.warning("Supervisor: memory consultation failed – %s", exc)
                job["_memory_context"] = {}
        
        with self._lock:
            self._active[job["id"]] = time.time()
        self.db.update_job(job["id"], status="running", stage="dispatch")
        try:
            self._pool.submit(self._run_job, job)
        except RuntimeError:
            self.db.update_job(job["id"], status="queued", stage=None)
            with self._lock:
                self._active.pop(job["id"], None)

    def _run_job(self, job: Dict[str, Any]) -> None:
        """
        Execute a single queued job.

        Retry policy
        ------------
        This method does NOT retry.  Retry responsibility is separated by layer:

        * **Worker-level retries** (``BaseWorker.with_retry``) handle transient
          tool failures (network timeouts, file-IO blips).  Max 3 attempts with
          exponential back-off, configured per-worker.

        * **StateGraph ``replan`` node** handles intelligent job-level replanning
          after agent failures.  It calls ``JarvisBrain.plan_execution`` with the
          failure context and re-routes the DAG.  Max attempts controlled by
          ``config.scheduler.max_attempts``.

        * **Supervisor (this method)** is a *scheduler only*.  It dispatches the
          job once, records the outcome, and returns.  Having three independent
          retry loops (worker + Jarvis + Supervisor) previously caused up to
          ``3 × 3 × 3 = 27`` attempts per transient failure and created race
          conditions where both Jarvis and the Supervisor set ``status='failed'``
          concurrently on the same DB row (W4).
        """
        job_id = job["id"]
        start_time = time.time()
        self.db.update_job(job_id, attempts=1)
        try:
            summary = self.pipeline.execute(job)
            elapsed = time.time() - start_time
            self.db.update_job(job_id, status="completed", stage="done",
                               result_json=json.dumps(summary), error=None)
            self.db.add_event(job_id, "Job completed", stage="done")
            # Legacy memory
            self.memory.remember(job_id, job["prompt"],
                                 summary.get("template", ""), "success", summary)
            # --- Jarvis Memory: record success ---
            if self.jarvis_memory:
                try:
                    assets_db = self.db.get_assets_for_job(job_id)
                    asset_names = [
                        f"{a.get('name','unknown')}:{a.get('source','unknown')}:{a.get('role','general')}"
                        for a in assets_db
                    ]
                    files = list(summary.get("generated_files", []))
                    workers_used = list(summary.get("workers_used",
                        ["internet", "analysis", "godot"]))
                    self.jarvis_memory.record_success(
                        job_id=job_id,
                        prompt=job["prompt"],
                        template_id=summary.get("template", "generic_scene"),
                        workers_used=workers_used,
                        assets_used=asset_names,
                        completion_time_secs=elapsed,
                        generated_files=files,
                        reliability_score=1.0,
                    )
                    # Record individual asset results
                    for a in assets_db:
                        self.jarvis_memory.record_asset_result(
                            asset_name=a.get("name", "unknown"),
                            asset_source=a.get("source", "unknown"),
                            category=a.get("role", "general"),
                            success=True,
                        )
                except Exception as mem_exc:
                    log.warning("[%s] Jarvis memory success record failed: %s", job_id[:8], mem_exc)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - start_time
            tb = traceback.format_exc()
            log.error("[%s] Job failed: %s", job_id, exc)
            self.db.add_event(job_id, f"Job failed: {exc}",
                              stage="error", level="error")
            self.db.update_job(job_id, status="failed", stage="error",
                               error=str(exc))
            self.memory.remember(job_id, job["prompt"], "", "failed",
                                 {"error": str(exc), "trace": tb[-1000:]})
            # --- Jarvis Memory: record failure ---
            if self.jarvis_memory:
                try:
                    self.jarvis_memory.record_failure(
                        prompt=job["prompt"],
                        worker="supervisor",
                        stage="pipeline",
                        error=str(exc),
                        stacktrace=tb,
                        fix_that_worked="",
                        retry_count=0,
                    )
                except Exception as mem_exc:
                    log.warning("[%s] Jarvis memory failure record failed: %s", job_id[:8], mem_exc)
        finally:
            with self._lock:
                self._active.pop(job_id, None)