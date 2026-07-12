import datetime
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from appsuite.config import load_config, PROJECT_ROOT
from appsuite.main import AppContext
from appsuite.core.health import WorkerHealthMonitor
from desktop_ui.state.event_bus import event_bus


class AppState(QObject):
    # PySide6 Signals to notify UI thread safely
    state_updated = Signal()
    job_completed = Signal(dict)  # Emitted with result dictionary
    backend_event_received = Signal(str, object)  # Bridge signal for background events

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True

        self.ctx: Optional[AppContext] = None
        self.active_project = "No Active Project"
        self.active_job_id: Optional[str] = None
        self.active_job_status = "Idle"
        self.jobs: List[Dict[str, Any]] = []
        self.timeline: List[Dict[str, Any]] = []
        self.current_inspector_data = {
            "stage": "None",
            "error": "None",
            "retry_count": 0,
            "worker": "None",
            "stacktrace": ""
        }
        
        # Initialize default workers dictionary
        self.workers = {
            "Supervisor": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 25.0, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "InternetWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 12.5, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "BlenderWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 450.2, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "GodotWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 180.4, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "ValidationWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 85.1, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "MemoryWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 42.0, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "PlannerWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 95.5, "success": 100.0, "failures": 0, "last_exec": "Never"},
            "AssetWorker": {"status": "Idle/Healthy", "task": "Idle", "cpu": 0.0, "ram": 64.0, "success": 100.0, "failures": 0, "last_exec": "Never"},
        }
        
        # Last run details for Output Viewer
        self.last_run_result: Optional[Dict[str, Any]] = None

        # Cached preflight health results (updated by background thread, read by Qt timer)
        self._health_cache: Dict[str, tuple] = {}  # worker_key -> (is_healthy, reason)
        self._health_cache_lock = threading.Lock()
        
        # Background polling thread (runs DB queries + health checks off the Qt thread)
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        # Connect the bridge signal to the handler running in the UI thread
        self.backend_event_received.connect(self._on_pyside_backend_event)

    def bootstrap(self) -> None:
        """Bootstraps the AppSuite backend context and loads config."""
        print("[AppState] Bootstrapping real AppSuite backend...")
        try:
            config = load_config()
            self.ctx = AppContext(config)
            self.ctx.start()
            print("[AppState] AppContext started successfully.")
            
            # Subscribe to the real backend event bus
            if self.ctx.event_bus:
                self.ctx.event_bus.subscribe("*", self._handle_backend_event)
                print("[AppState] Subscribed to backend event bus.")
            
            # Do an initial non-blocking DB load
            self.refresh_from_db()
            
            # Start background polling thread (keeps DB + health off the Qt thread)
            self._poll_stop.clear()
            self._poll_thread = threading.Thread(
                target=self._background_poll_loop, daemon=True, name="appsuite-ui-poll"
            )
            self._poll_thread.start()
            print("[AppState] Background poll thread started.")
            
        except Exception as e:
            print(f"[AppState] Error during bootstrap: {e}")
            import traceback
            traceback.print_exc()

    def shutdown(self) -> None:
        """Stops the backend services cleanly."""
        self._poll_stop.set()  # Stop background poll thread
        if self.ctx:
            print("[AppState] Shutting down AppSuite background services...")
            try:
                self.ctx.shutdown()
                print("[AppState] AppSuite services stopped.")
            except Exception as e:
                print(f"[AppState] Error during shutdown: {e}")

    def _background_poll_loop(self) -> None:
        """Runs in a daemon thread. Performs all blocking I/O (DB + health) every 2s."""
        while not self._poll_stop.is_set():
            try:
                self._background_poll_tick()
            except Exception as e:
                print(f"[AppState] Poll tick error: {e}")
            self._poll_stop.wait(2.0)  # poll every 2 seconds

    def _background_poll_tick(self) -> None:
        """Does all blocking work: DB queries + preflight health checks."""
        if not self.ctx:
            return

        # 1. Run preflight health checks (reads disk + config — blocks!)
        worker_health_keys = {
            "InternetWorker": "internet",
            "BlenderWorker": "blender",
            "GodotWorker": "godot",
            "ValidationWorker": "validation",
            "AssetWorker": "analysis",
        }
        new_health: Dict[str, tuple] = {}
        for ui_name, backend_key in worker_health_keys.items():
            try:
                result = WorkerHealthMonitor.preflight_check(backend_key)
            except Exception as e:
                result = (False, str(e))
            new_health[backend_key] = result
        with self._health_cache_lock:
            self._health_cache = new_health

        # 2. Run DB queries (SQLite reads — blocks!)
        self.refresh_from_db()

    def _handle_backend_event(self, event_type: str, data: Any) -> None:
        """Backend pub-sub listener (invoked from background threads). Bridge to UI thread."""
        self.backend_event_received.emit(event_type, data)

    def _on_pyside_backend_event(self, event_type: str, data: Any) -> None:
        """Handles backend events in the UI thread context."""
        # Route event type
        if event_type in ("JOB_STARTED", "task_dequeued"):
            job_id = data.get("job_id") if isinstance(data, dict) else str(data)
            self.add_timeline_event(f"Job {job_id[:8]} started", "INFO", stage="orchestration", worker="Supervisor")
        elif event_type in ("JOB_FINISHED", "task_completed"):
            job_id = data.get("job_id") if isinstance(data, dict) else str(data)
            self.add_timeline_event(f"Job {job_id[:8]} completed successfully", "INFO", stage="done", worker="Supervisor")
            self.refresh_from_db()
        elif event_type in ("JOB_FAILED", "task_failed"):
            job_id = data.get("job_id") if isinstance(data, dict) else ""
            error_msg = data.get("error") if isinstance(data, dict) else str(data)
            self.add_timeline_event(f"Job failed: {error_msg}", "ERROR", stage="error", worker="Supervisor", error=error_msg)
            self.update_inspector(
                stage="error",
                error=error_msg,
                retry_count=1,
                worker="Supervisor",
                stacktrace=data.get("traceback", "No traceback available.") if isinstance(data, dict) else ""
            )
            self.refresh_from_db()
        elif event_type == "WORKER_STARTED":
            w_name = data.get("worker_name", "UnknownWorker")
            task_id = data.get("task_id", "")
            self.add_timeline_event(f"Worker {w_name} started executing task {task_id[:8]}", "INFO", stage="orchestration", worker=w_name)
            # Find and update worker status to running
            ui_name = self._map_worker_key(w_name)
            if ui_name in self.workers:
                self.workers[ui_name]["status"] = "Running"
                self.workers[ui_name]["task"] = f"Running task {task_id[:8]}"
            self.state_updated.emit()
        elif event_type == "WORKER_FINISHED":
            w_name = data.get("worker_name", "UnknownWorker")
            duration = data.get("duration", 0.0)
            self.add_timeline_event(f"Worker {w_name} finished in {duration:.2f}s", "INFO", stage="orchestration", worker=w_name)
            # Find and update worker status to idle
            ui_name = self._map_worker_key(w_name)
            if ui_name in self.workers:
                self.workers[ui_name]["status"] = "Idle/Healthy"
                self.workers[ui_name]["task"] = "Idle"
            self.state_updated.emit()
        elif event_type == "RESOURCE_UPDATED":
            # Direct resource telemetry event
            pass
        elif event_type == "VALIDATION_FAILED":
            job_id = data.get("job_id", "")
            error_msg = data.get("error", "Layout visual overlap detected.")
            self.add_timeline_event(f"Validation warning: {error_msg}", "WARNING", stage="output_validation", worker="ValidationWorker", error=error_msg)
            self.update_inspector(
                stage="output_validation",
                error=error_msg,
                retry_count=1,
                worker="ValidationWorker",
                stacktrace="Overlap check failure in generated level structure."
            )
            self.state_updated.emit()

        # Publish internally to desktop UI event bus
        event_bus.publish(event_type, data)

    def _map_worker_key(self, name: str) -> str:
        """Map worker strings to UI display names."""
        mapping = {
            "internet": "InternetWorker",
            "blender": "BlenderWorker",
            "godot": "GodotWorker",
            "validation": "ValidationWorker",
            "analysis": "AssetWorker",
            "code": "PlannerWorker",
            "memory": "MemoryWorker",
            "supervisor": "Supervisor"
        }
        return mapping.get(name.lower(), name)

    def set_active_project(self, name: str) -> None:
        self.active_project = name
        event_bus.publish("PROJECT_CHANGED", {"project": name})

    def add_timeline_event(self, event: str, level: str = "INFO", stage: str = "system", worker: str = "orchestrator", error: str = "None", stacktrace: str = "") -> None:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        evt = {
            "timestamp": now,
            "event": event,
            "level": level,
            "stage": stage,
            "worker": worker,
            "error": error,
            "stacktrace": stacktrace
        }
        self.timeline.append(evt)
        event_bus.publish("TIMELINE_UPDATED", evt)

    def update_inspector(self, stage: str, error: str, retry_count: int, worker: str, stacktrace: str) -> None:
        self.current_inspector_data = {
            "stage": stage,
            "error": error,
            "retry_count": retry_count,
            "worker": worker,
            "stacktrace": stacktrace
        }
        event_bus.publish("INSPECTOR_UPDATED", self.current_inspector_data)

    def run_prompt(self, prompt: str) -> str:
        """Submit a prompt runner job to the Supervisor."""
        if not self.ctx:
            raise RuntimeError("AppState not bootstrapped.")
        
        # Submit via supervisor scheduler
        job_id = self.ctx.supervisor.submit(prompt)
        self.active_job_id = job_id
        self.active_job_status = "Running"
        self.add_timeline_event(f"Submitted prompt: {prompt}", stage="planning", worker="Supervisor")
        
        # Launch a daemon observer thread to watch for completion & fetch results
        threading.Thread(target=self._watch_job_execution, args=(job_id,), daemon=True).start()
        
        self.refresh_from_db()
        return job_id

    def pause_job(self, job_id: str) -> None:
        if self.ctx and self.ctx.project_manager:
            self.ctx.project_manager.pause_project(job_id)
            self.add_timeline_event(f"Paused job {job_id[:8]}", "WARNING", stage="orchestration", worker="Supervisor")
            self.refresh_from_db()

    def resume_job(self, job_id: str) -> None:
        if self.ctx and self.ctx.project_manager:
            self.ctx.project_manager.resume_project(job_id)
            self.add_timeline_event(f"Resumed job {job_id[:8]}", "INFO", stage="orchestration", worker="Supervisor")
            self.refresh_from_db()

    def cancel_job(self, job_id: str) -> None:
        if self.ctx and self.ctx.db:
            self.ctx.db.update_job(job_id, status="failed", error="Cancelled by user")
            self.ctx.db.add_event(job_id, "Job cancelled by user", stage="system", level="error")
            self.add_timeline_event(f"Cancelled job {job_id[:8]}", "ERROR", stage="system", worker="Supervisor")
            self.refresh_from_db()

    def _watch_job_execution(self, job_id: str) -> None:
        """Polls the database for job completion/failure to build Phase 8 result details."""
        if not self.ctx:
            return
        
        print(f"[AppState] Watching job {job_id[:8]}...")
        start_time = time.time()
        
        while True:
            time.sleep(1.0)
            if not self.ctx:
                break
            
            job = self.ctx.db.get_job(job_id)
            if not job:
                continue
                
            status = job.get("status")
            if status in ("completed", "failed"):
                # Job is finished! Let's fetch metrics and assets
                elapsed = time.time() - start_time
                assets = self.ctx.db.get_assets_for_job(job_id)
                
                # Fetch result json if success
                result_json = {}
                if job.get("result_json"):
                    try:
                        result_json = json.loads(job["result_json"])
                    except Exception:
                        pass
                
                # Count meshes/textures
                mesh_count = sum(1 for a in assets if a.get("format", "").lower() in ("glb", "gltf", "obj", "fbx"))
                texture_count = sum(1 for a in assets if a.get("format", "").lower() in ("png", "jpg", "jpeg", "tga"))
                
                # Resolve Godot project directory and main scene path
                output_dir = self.ctx.config.abs_path("output_dir")
                project_dir = output_dir / "projects" / job_id
                main_scene = project_dir / "Scenes" / "main.tscn"
                
                res_details = {
                    "job_id": job_id,
                    "prompt": job.get("prompt"),
                    "status": status,
                    "godot_project": str(project_dir),
                    "main_scene": str(main_scene) if main_scene.exists() else None,
                    "asset_count": len(assets),
                    "mesh_count": mesh_count,
                    "texture_count": texture_count,
                    "duration_seconds": elapsed,
                    "generated_files": [str(p.relative_to(PROJECT_ROOT)) for p in project_dir.rglob("*") if p.is_file()] if project_dir.exists() else []
                }
                
                self.last_run_result = res_details
                self.job_completed.emit(res_details)
                
                event_bus.publish("JOB_FINISHED", {"job_id": job_id, "status": status, "result": res_details})
                self.add_timeline_event(f"Job {job_id[:8]} finished with status: {status.upper()}", "INFO" if status == "completed" else "ERROR", stage="done", worker="Supervisor")
                break

    def refresh_from_db(self) -> None:
        """Loads jobs and timeline logs from the SQLite database."""
        if not self.ctx:
            return

        # 1. Update jobs list
        db_jobs = self.ctx.db.list_jobs(50)
        new_jobs = []
        for j in db_jobs:
            # Format timestamp
            dt = datetime.datetime.fromtimestamp(j["created_at"])
            ts = dt.strftime("%H:%M")
            new_jobs.append({
                "id": j["id"],
                "prompt": j["prompt"],
                "status": j["status"],
                "time": ts,
                "progress": j.get("progress", 0.0),
                "error": j.get("error")
            })
        self.jobs = new_jobs

        # 2. Update active job details if running
        running_jobs = [j for j in self.jobs if j["status"] == "running"]
        if running_jobs:
            self.active_job_id = running_jobs[0]["id"]
            self.active_job_status = "Running"
        else:
            self.active_job_status = "Idle"

        # 3. Update timeline events (merging SQLite events + local UI events)
        # Fetch events for the active job, or all recent events if none active
        active_id = self.active_job_id or (self.jobs[0]["id"] if self.jobs else None)
        
        db_events = []
        if active_id:
            db_events = self.ctx.db.get_events(active_id)
            
        new_timeline = []
        for e in db_events:
            dt = datetime.datetime.fromtimestamp(e["created_at"])
            ts = dt.strftime("%H:%M:%S")
            level = e["level"].upper()
            stage = e["stage"] or "system"
            
            # Map stages to specific workers for visual clarity
            worker_map = {
                "planning": "PlannerWorker",
                "queue": "Supervisor",
                "asset_search": "InternetWorker",
                "asset_processing": "AssetWorker",
                "blender_import": "BlenderWorker",
                "godot_import": "GodotWorker",
                "output_validation": "ValidationWorker",
                "memory": "MemoryWorker",
            }
            worker = worker_map.get(stage, "Supervisor")
            
            new_timeline.append({
                "timestamp": ts,
                "event": e["message"],
                "level": level,
                "stage": stage,
                "worker": worker,
                "error": "None" if level != "ERROR" else e["message"],
                "stacktrace": ""
            })
            
        # Append UI local events if they aren't already included
        for local_evt in self.timeline:
            if not any(x["event"] == local_evt["event"] and x["timestamp"] == local_evt["timestamp"] for x in new_timeline):
                new_timeline.append(local_evt)
                
        # Sort combined timeline by timestamp
        new_timeline.sort(key=lambda x: x["timestamp"])
        self.timeline = new_timeline

        # 4. Refresh worker health/statuses (wrapped to prevent any error from crashing the UI)
        try:
            self.update_worker_health()
        except Exception as e:
            print(f"[AppState] update_worker_health error (non-fatal): {e}")

        self.state_updated.emit()

    def update_worker_health(self) -> None:
        """Updates worker statuses from cached health results (safe to call from any thread)."""
        if not self.ctx:
            return

        # Read cached preflight results (populated by background thread)
        with self._health_cache_lock:
            health_snapshot = dict(self._health_cache)

        # Try to read worker_statistics.json from output directory
        stats_path = self.ctx.config.abs_path("output_dir") / "worker_statistics.json"
        stats = {}
        if stats_path.exists():
            try:
                with open(stats_path, "r", encoding="utf-8") as f:
                    stats = json.load(f)
            except Exception:
                pass

        worker_health_keys = {
            "InternetWorker": "internet",
            "BlenderWorker": "blender",
            "GodotWorker": "godot",
            "ValidationWorker": "validation",
            "AssetWorker": "analysis",
        }

        # Snapshot active job IDs WITHOUT holding the lock during DB calls
        active_job_ids = []
        if self.ctx.supervisor._thread and self.ctx.supervisor._thread.is_alive():
            with self.ctx.supervisor._lock:
                active_job_ids = list(self.ctx.supervisor._active.keys())
            supervisor_status = "Running" if active_job_ids else "Idle/Healthy"
        else:
            supervisor_status = "Idle/Healthy"
        self.workers["Supervisor"]["status"] = supervisor_status
        self.workers["Supervisor"]["task"] = "Orchestrating" if supervisor_status == "Running" else "Idle"

        self.workers["MemoryWorker"]["status"] = "Idle/Healthy"
        self.workers["PlannerWorker"]["status"] = "Idle/Healthy"

        for ui_name, backend_key in worker_health_keys.items():
            # Use cached health result — no blocking I/O here
            is_healthy, reason = health_snapshot.get(backend_key, (True, "OK"))

            # Check running state from already-snapshotted active job IDs (no lock needed)
            is_running = False
            active_task_name = "Idle"
            try:
                for job_id in active_job_ids:
                    job = self.ctx.db.get_job(job_id)
                    if job and job.get("stage") == backend_key:
                        is_running = True
                        active_task_name = f"Processing Job {job_id[:8]}"
                        break
            except Exception:
                pass

            if is_running:
                status = "Running"
            elif is_healthy:
                status = "Idle/Healthy"
            else:
                status = f"Failed ({reason})"

            w_stats = stats.get(backend_key, stats.get(ui_name, {}))
            total_runs = w_stats.get("total_runs", 0)
            success_runs = w_stats.get("success_runs", 0)
            failures = w_stats.get("failure_runs", 0)
            success_rate = round((success_runs / total_runs) * 100.0, 1) if total_runs > 0 else 100.0

            self.workers[ui_name]["status"] = status
            self.workers[ui_name]["task"] = active_task_name
            self.workers[ui_name]["success"] = success_rate
            self.workers[ui_name]["failures"] = failures
            self.workers[ui_name]["last_exec"] = "Recent" if total_runs > 0 else "Never"


# Singleton app state
app_state = AppState()
