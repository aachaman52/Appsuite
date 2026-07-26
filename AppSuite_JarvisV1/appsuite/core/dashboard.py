from __future__ import annotations
import os
import psutil
from typing import Any, Dict, Optional

# Failsafe imports for environment flexibility
try:
    from fastapi import FastAPI, APIRouter
except ImportError:
    # Fallback mock for testing/compilation without FastAPI installed
    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.routes = []
        def get(self, path: str, *args, **kwargs):
            class Route:
                def __init__(self, p, f):
                    self.path = p
                    self.endpoint = f
            def decorator(func):
                self.routes.append(Route(path, func))
                return func
            return decorator
    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = []
        def include_router(self, router, *args, **kwargs):
            if hasattr(router, "routes"):
                self.routes.extend(router.routes)

class DashboardApp:
    """FastAPI dashboard backend exposing runtime metrics and OS component states."""
    
    def __init__(self, ctx: Any, event_bus: Any = None) -> None:
        self.ctx = ctx
        self.event_bus = event_bus
        self.live_state = {
            "pipeline_progress": 0.0,
            "worker_status": {},
            "current_stage": "idle",
            "eta_seconds": 0,
            "downloads": 0,
            "validation_score": 0.0,
            "repair_count": 0
        }
        if self.event_bus:
            self.event_bus.subscribe("WorkerStarted", self._on_worker_started)
            self.event_bus.subscribe("WorkerFinished", self._on_worker_finished)
            self.event_bus.subscribe("WorkerFailed", self._on_worker_failed)
            self.event_bus.subscribe("PipelineCompleted", self._on_pipeline_completed)
            
        self.app = FastAPI(title="AppSuite Jarvis V1 Dashboard Backend", version="11.0.0")
        self.router = APIRouter()
        self._setup_routes()
        self.app.include_router(self.router)
        
    def _setup_routes(self) -> None:
        
        @self.router.get("/api/health")
        def health():
            gpu_percent = 0.0
            try:
                # Naive GPU check via nvidia-smi if available, for quick stats
                import subprocess
                res = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=1)
                gpu_percent = float(res.stdout.strip().split('\n')[0])
            except Exception:
                pass
                
            return {
                "status": "healthy",
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "gpu_percent": gpu_percent,
                "pid": os.getpid()
            }
            
        @self.router.get("/api/live_state")
        def get_live_state():
            return self.live_state
            
        @self.router.get("/api/jobs")
        def list_jobs():
            try:
                return self.ctx.db.list_jobs(limit=50)
            except Exception:
                return []
                
        @self.router.get("/api/queue")
        def get_queue():
            try:
                # If persistent task queue is wired
                if hasattr(self.ctx, "task_queue") and self.ctx.task_queue:
                    return self.ctx.task_queue.list_tasks()
            except Exception:
                pass
            return []
            
        @self.router.get("/api/providers")
        def list_providers():
            try:
                return self.ctx.provider_manager.status()
            except Exception:
                return []
                
        @self.router.get("/api/projects")
        def list_projects():
            try:
                if hasattr(self.ctx, "project_workspace") and self.ctx.project_workspace:
                    projects = self.ctx.project_workspace.list_projects()
                    # Calculate progress for each project
                    for p in projects:
                        if hasattr(self.ctx, "goal_manager") and self.ctx.goal_manager:
                            p["progress"] = self.ctx.goal_manager.get_progress(p["project_id"])
                        else:
                            p["progress"] = 0.0
                    return projects
            except Exception:
                pass
            return []

        @self.router.get("/api/benchmarks")
        def list_benchmarks():
            try:
                if hasattr(self.ctx, "benchmark_engine") and self.ctx.benchmark_engine:
                    return {
                        "latency": self.ctx.benchmark_engine.get_rolling_stats("latency"),
                        "cost": self.ctx.benchmark_engine.get_rolling_stats("cost"),
                        "failures": self.ctx.benchmark_engine.get_rolling_stats("failure")
                    }
            except Exception:
                pass
            return {}

        @self.router.get("/api/workers")
        def list_workers():
            try:
                if hasattr(self.ctx, "registry") and self.ctx.registry:
                    # Return worker scores from Registry
                    scores = {}
                    for agent_type in ["asset", "blender", "godot", "browser", "validation"]:
                        scores[agent_type] = self.ctx.registry.get_scores_for_agent(agent_type)
                    return scores
            except Exception:
                pass
            return {}

    def _on_worker_started(self, event: Dict[str, Any]) -> None:
        self.live_state["current_stage"] = event.get("worker", "unknown")
        self.live_state["worker_status"][event.get("worker", "unknown")] = "running"
        
    def _on_worker_finished(self, event: Dict[str, Any]) -> None:
        worker = event.get("worker", "unknown")
        self.live_state["worker_status"][worker] = "completed"
        # Dummy progress bump based on worker list length (assume ~7 workers)
        self.live_state["pipeline_progress"] += (100.0 / 7.0)
        
    def _on_worker_failed(self, event: Dict[str, Any]) -> None:
        self.live_state["worker_status"][event.get("worker", "unknown")] = "failed"
        self.live_state["repair_count"] += 1
        
    def _on_pipeline_completed(self, event: Dict[str, Any]) -> None:
        self.live_state["current_stage"] = "completed" if event.get("success") else "failed"
        self.live_state["pipeline_progress"] = 100.0 if event.get("success") else self.live_state["pipeline_progress"]
