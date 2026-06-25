"""REST API endpoints."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ..models import (AssetResponse, JobCreateRequest, JobEvent, JobResponse,
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

    @router.post("/jobs", response_model=JobResponse, status_code=201)
    def create_job(req: JobCreateRequest) -> JobResponse:
        job_id = app_ctx.supervisor.submit(req.prompt, req.template_id)
        return _job_to_response(db.get_job(job_id))

    @router.get("/jobs", response_model=List[JobResponse])
    def list_jobs(limit: int = 100) -> List[JobResponse]:
        return [_job_to_response(r) for r in db.list_jobs(limit)]

    @router.get("/jobs/{job_id}", response_model=JobResponse)
    def get_job(job_id: str) -> JobResponse:
        row = db.get_job(job_id)
        if not row:
            raise HTTPException(404, "Job not found")
        return _job_to_response(row)

    @router.get("/jobs/{job_id}/events", response_model=List[JobEvent])
    def get_events(job_id: str) -> List[JobEvent]:
        if not db.get_job(job_id):
            raise HTTPException(404, "Job not found")
        return [JobEvent(**e) for e in db.get_events(job_id)]

    @router.get("/jobs/{job_id}/assets", response_model=List[AssetResponse])
    def get_assets(job_id: str) -> List[AssetResponse]:
        return [
            AssetResponse(
                id=a["id"], role=a.get("role"), name=a.get("name"), source=a.get("source"),
                format=a.get("format"), quality_score=a.get("quality_score"),
                file_path=a.get("file_path"),
            )
            for a in db.get_assets_for_job(job_id)
        ]

    @router.get("/templates")
    def list_templates() -> List[Dict[str, Any]]:
        return app_ctx.templates.list()

    @router.get("/memory")
    def memory(limit: int = 50) -> List[Dict[str, Any]]:
        return app_ctx.memory.recall(limit)

    @router.get("/providers")
    def providers() -> List[Dict[str, Any]]:
        return app_ctx.provider_manager.status()

    @router.get("/plugins")
    def plugins() -> List[str]:
        return app_ctx.plugins.list()

    @router.get("/assets", response_model=List[AssetResponse])
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

    @router.get("/status", response_model=SystemStatus)
    def status() -> SystemStatus:
        snap = app_ctx.jarvis.snapshot()
        return SystemStatus(
            app="AppSuite", version=app_ctx.version,
            uptime_seconds=snap["uptime_seconds"],
            resources=snap["resources"],
            workers={"registered": list(app_ctx.workers.keys()),
                     "scheduling_allowed": snap["scheduling_allowed"],
                     "scheduling_reason": snap["scheduling_reason"]},
            jobs=app_ctx.supervisor.status(),
            providers=app_ctx.provider_manager.status(),
        )

    @router.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    # ── Jarvis orchestration endpoints ────────────────────────────────────────

    @router.get("/jarvis/status")
    def jarvis_status() -> Dict[str, Any]:
        """Full Jarvis status: resources + wiring + scheduling gate."""
        return app_ctx.jarvis.status()

    @router.post("/jarvis/run")
    def jarvis_run(req: JobCreateRequest) -> Dict[str, Any]:
        """
        Trigger a full Jarvis-orchestrated pipeline run synchronously.
        Returns a JarvisResult dict.

        Note: For long-running jobs prefer POST /jobs (queued via Supervisor).
        Use this endpoint for direct / immediate runs.
        """
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

    @router.get("/jarvis/plan")
    def jarvis_plan(prompt: str, template_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Preview what Jarvis would do for a given prompt — without executing anything.
        Returns the JarvisPlan as a dict.
        """
        # Access the private _plan method — this is intentionally safe (read-only)
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

    @router.get("/jarvis/memory")
    def jarvis_memory(limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent Jarvis memory entries (prompt -> outcome history)."""
        return app_ctx.memory.recall(limit)

    return router
