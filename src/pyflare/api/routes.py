"""REST API endpoints for PyFlare."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from .auth import verify_api_key
from ..core.models import (AssetResponse, JobCreateRequest, JobEvent, JobResponse,
                      SystemStatus)


def build_router(app_ctx) -> APIRouter:
    router = APIRouter()
    db = app_ctx.db

    def _job_to_response(row: Dict[str, Any]) -> JobResponse:
        result = json.loads(row["result_json"]) if row.get("result_json") else None
        return JobResponse(
            id=row["id"], prompt=row["prompt"], status=row["status"], stage=row.get("stage"),
            progress=row.get("progress", 0.0), template_id=row.get("template_id"),
            attempts=row.get("attempts", 0), error=row.get("error"), result=result,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # ── Public Endpoints ────────────────────────────────────────────────────────

    @router.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "product": "PyFlare"}

    @router.get("/status", response_model=SystemStatus)
    def status() -> SystemStatus:
        snap = app_ctx.jarvis.snapshot()
        version = getattr(app_ctx, "version", "1.0.0")
        return SystemStatus(
            app="PyFlare", version=version,
            uptime_seconds=snap.get("uptime_seconds", 0.0),
            resources=snap.get("resources", {}),
            workers={"registered": list(app_ctx.workers.keys()) if hasattr(app_ctx, "workers") else [],
                     "scheduling_allowed": snap.get("scheduling_allowed", True),
                     "scheduling_reason": snap.get("scheduling_reason", "ok")},
            jobs=app_ctx.supervisor.status() if hasattr(app_ctx, "supervisor") else {},
            providers=app_ctx.provider_manager.status() if hasattr(app_ctx, "provider_manager") else [],
        )

    # ── Protected Endpoints (Require API Key when configured) ────────────────────

    @router.post("/jobs", response_model=JobResponse, status_code=201, dependencies=[Depends(verify_api_key)])
    def create_job(req: JobCreateRequest) -> JobResponse:
        job_id = app_ctx.supervisor.submit(req.prompt, req.template_id)
        return _job_to_response(db.get_job(job_id))

    @router.get("/jobs", response_model=List[JobResponse], dependencies=[Depends(verify_api_key)])
    def list_jobs(limit: int = 100) -> List[JobResponse]:
        return [_job_to_response(r) for r in db.list_jobs(limit)]

    @router.get("/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(verify_api_key)])
    def get_job(job_id: str) -> JobResponse:
        row = db.get_job(job_id)
        if not row:
            raise HTTPException(404, "Job not found")
        return _job_to_response(row)

    @router.get("/jobs/{job_id}/events", response_model=List[JobEvent], dependencies=[Depends(verify_api_key)])
    def get_events(job_id: str) -> List[JobEvent]:
        if not db.get_job(job_id):
            raise HTTPException(404, "Job not found")
        return [JobEvent(**e) for e in db.get_events(job_id)]

    @router.get("/jobs/{job_id}/assets", response_model=List[AssetResponse], dependencies=[Depends(verify_api_key)])
    def get_assets(job_id: str) -> List[AssetResponse]:
        return [
            AssetResponse(
                id=a["id"], role=a.get("role"), name=a.get("name"), source=a.get("source"),
                format=a.get("format"), quality_score=a.get("quality_score"),
                file_path=a.get("file_path"),
            )
            for a in db.get_assets_for_job(job_id)
        ]

    @router.get("/templates", dependencies=[Depends(verify_api_key)])
    def list_templates() -> List[Dict[str, Any]]:
        return app_ctx.templates.list()

    @router.get("/memory", dependencies=[Depends(verify_api_key)])
    def memory(limit: int = 50) -> List[Dict[str, Any]]:
        return app_ctx.memory.recall(limit)

    @router.get("/providers", dependencies=[Depends(verify_api_key)])
    def providers() -> List[Dict[str, Any]]:
        return app_ctx.provider_manager.status()

    @router.get("/plugins", dependencies=[Depends(verify_api_key)])
    def plugins() -> List[str]:
        return app_ctx.plugins.list()

    @router.get("/assets", response_model=List[AssetResponse], dependencies=[Depends(verify_api_key)])
    def list_all_assets(limit: int = 200, search: Optional[str] = None) -> List[AssetResponse]:
        """List all registered assets across all jobs, with optional name/source search."""
        rows = db.list_assets(limit=limit, search=search)
        return [
            AssetResponse(
                id=a["id"], role=a.get("role"), name=a.get("name"), source=a.get("source"),
                format=a.get("format"), quality_score=a.get("quality_score"),
                file_path=a.get("file_path"),
            )
            for a in rows
        ]

    # ── PyFlare / Jarvis orchestration endpoints ──────────────────────────────

    @router.get("/jarvis/status", dependencies=[Depends(verify_api_key)])
    def jarvis_status() -> Dict[str, Any]:
        """Full engine status: resources + wiring + scheduling gate."""
        return app_ctx.jarvis.status()

    @router.post("/jarvis/run", dependencies=[Depends(verify_api_key)])
    def jarvis_run(req: JobCreateRequest) -> Dict[str, Any]:
        """Trigger a full pipeline run synchronously."""
        try:
            result = app_ctx.jarvis.run(
                prompt=req.prompt,
                template_id=req.template_id,
            )
            return result.to_dict()
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))
        except Exception as exc:
            raise HTTPException(500, str(exc))

    @router.get("/jarvis/plan", dependencies=[Depends(verify_api_key)])
    def jarvis_plan(prompt: str, template_id: Optional[str] = None) -> Dict[str, Any]:
        """Preview execution plan for a prompt without executing."""
        plan = app_ctx.jarvis._plan(prompt, template_id)
        return {
            "prompt":            plan.prompt,
            "template_id":       plan.template_id,
            "scene_plan":        plan.scene_plan,
            "use_cached_assets": plan.use_cached_assets,
            "cached_job_id":     plan.cached_job_id,
            "workers_to_run":    plan.workers_to_run,
            "reasons":           plan.reasons,
        }

    # ── Deterministic Router Endpoints ──────────────────────────────────────────

    @router.post("/router/plan", response_model=Dict[str, Any])
    def router_plan(task: Dict[str, Any]) -> Dict[str, Any]:
        """Preview deterministic routing decision for a given task specification."""
        from pyflare.router import DeterministicRouter, TaskSpec
        spec = TaskSpec(**task) if isinstance(task, dict) else task
        router_engine = getattr(app_ctx, "router", None) or DeterministicRouter(hardware_manager=getattr(app_ctx, "hardware", None))
        decision = router_engine.plan_route(spec)
        return decision.model_dump()

    @router.post("/router/execute", response_model=Dict[str, Any], dependencies=[Depends(verify_api_key)])
    def router_execute(task: Dict[str, Any]) -> Dict[str, Any]:
        """Plan and execute a task through the deterministic router with fallbacks."""
        from pyflare.router import DeterministicRouter, RouterExecutor, TaskSpec
        spec = TaskSpec(**task) if isinstance(task, dict) else task
        router_engine = getattr(app_ctx, "router", None) or DeterministicRouter(hardware_manager=getattr(app_ctx, "hardware", None))
        decision = router_engine.plan_route(spec)
        executor = getattr(app_ctx, "router_executor", None) or RouterExecutor()
        result = executor.execute(spec, decision)
        return result.model_dump()

    @router.get("/router/capabilities")
    def router_capabilities() -> List[Dict[str, Any]]:
        """List all registered candidate capabilities and current availability."""
        from pyflare.router import CapabilityRegistry
        reg = getattr(app_ctx, "router_registry", None) or CapabilityRegistry()
        return [c.model_dump() for c in reg.list_candidates()]

    @router.get("/router/hardware")
    def router_hardware() -> Dict[str, Any]:
        """Inspect host hardware profile and detection telemetry."""
        from pyflare.core.hardware_manager import HardwareManager
        hw_mgr = getattr(app_ctx, "hardware", None) or HardwareManager({})
        profile = hw_mgr.get_hardware_profile()
        return profile.model_dump()

    @router.get("/router/history", dependencies=[Depends(verify_api_key)])
    def router_history(limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent routing history records and telemetry."""
        from pyflare.router import RouterHistoryTracker
        tracker = getattr(app_ctx, "router_history", None) or RouterHistoryTracker()
        return tracker.list_history(limit=limit)

    return router
