"""Pipeline definition: ordered stages from prompt to playable scene.

Memory system is now active: if a prior successful job used the same prompt,
the pipeline reuses its asset paths instead of re-downloading.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..logging_setup import get_logger
from ..core.project import Project
from ..core.asset_router import AssetRouter
from ..core.asset_normalizer import AssetNormalizer

log = get_logger("pipeline")


class Pipeline:
    def __init__(self, db, registry, memory, templates, plugins, workers: Dict[str, Any],
                 output_dir: Path):
        self.db = db
        self.registry = registry
        self.memory = memory
        self.templates = templates
        self.plugins = plugins
        self.workers = workers
        self.output_dir = Path(output_dir)
        # Ordered pipeline stages: (stage_label, worker_key).
        self.stages: List[Tuple[str, str]] = [
            ("asset_search", "internet"),
            ("asset_processing", "analysis"),
            ("blender_import", "blender"),
            ("godot_import", "godot"),
            ("output_validation", "validation"),
            ("cloud_deploy", "deploy"),
        ]

    def _try_reuse_prior_assets(
        self, job_id: str, prompt: str, state: Dict[str, Any]
    ) -> bool:
        """
        If a prior successful run exists for this prompt, attempt to reuse
        its registered assets. Returns True if reuse was successful.
        """
        prior = self.memory.recall_similar(prompt)
        if not prior:
            return False

        prior_job_id = prior.get("job_id")
        if not prior_job_id:
            return False

        prior_assets = self.registry.for_job(prior_job_id)
        if not prior_assets:
            return False

        # Verify all prior asset files still exist on disk
        valid_assets = []
        for a in prior_assets:
            fp = Path(a.get("file_path", ""))
            if fp.exists() and fp.stat().st_size > 0:
                valid_assets.append(a)

        if not valid_assets:
            log.info("[%s] Prior assets for job %s are missing on disk; re-fetching",
                     job_id, prior_job_id[:8])
            return False

        log.info(
            "[%s] Reusing %d assets from prior job %s",
            job_id, len(valid_assets), prior_job_id[:8],
        )
        self.db.add_event(
            job_id,
            f"Reusing {len(valid_assets)} assets from prior successful job {prior_job_id[:8]}",
            stage="memory",
        )
        state["assets"] = [dict(a) for a in valid_assets]
        return True

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = job["id"]
        template = self.templates.resolve(job["prompt"], job.get("template_id"))
        self.db.update_job(job_id, template_id=template["id"])
        self.db.add_event(job_id, f"Resolved template '{template['id']}'", stage="prompt")
        log.info("[%s] template=%s prompt=%r", job_id, template["id"], job["prompt"])

        # Initialize Project System
        project = Project(job_id, self.output_dir / "projects")
        project.setup_directories()

        state: Dict[str, Any] = {"template": template, "assets": []}
        state.update(project.get_state_dict())
        state["project"] = project
        state["normalized_assets"] = []

        # --- Memory: try to reuse assets from a prior identical prompt -------
        assets_reused = self._try_reuse_prior_assets(job_id, job["prompt"], state)
        if assets_reused:
            normalizer = AssetNormalizer(Path(state["assets_path"]) / "Normalized")
            state["assets"] = normalizer.normalize_many(
                state["assets"], job_id=job_id, prompt=job["prompt"]
            )
            state["normalized_assets"] = [
                a.get("normalized_asset") for a in state["assets"]
            ]
            self.db.add_event(
                job_id,
                f"Normalized {len(state['assets'])} reused assets into package manifests",
                stage="asset_normalization",
            )
            AssetRouter.route_assets(state["assets"])

        ordered = self.stages
        results: Dict[str, Any] = {}
        total = len(ordered)

        for idx, (stage, worker_key) in enumerate(ordered, start=1):
            # Skip asset_search if we reused prior assets
            if stage == "asset_search" and assets_reused:
                results[stage] = {"assets_fetched": len(state["assets"]), "reused": True}
                self.db.add_event(job_id, "Skipped asset_search: reusing prior assets", stage=stage)
                self.db.update_job(job_id, stage=stage, progress=round((idx - 1) / total, 2))
                continue

            worker = self.workers[worker_key]
            self.db.update_job(job_id, stage=stage, progress=round((idx - 1) / total, 2))
            self.db.add_event(job_id, f"Stage start: {stage}", stage=stage)
            log.info("[%s] stage %s started", job_id, stage)

            t0 = time.monotonic()
            out = worker.run(job, state)
            duration = time.monotonic() - t0

            results[stage] = out
            log.info("[%s] stage %s completed in %.3fs", job_id, stage, duration)
            self.db.add_event(
                job_id,
                f"Stage done: {stage} in {duration:.3f}s -> {json.dumps(out)[:300]}",
                stage=stage,
            )

            # Route assets if they were just fetched
            if stage == "asset_search":
                normalizer = AssetNormalizer(Path(state["assets_path"]) / "Normalized")
                state["assets"] = normalizer.normalize_many(
                    state["assets"], job_id=job_id, prompt=job["prompt"]
                )
                state["normalized_assets"] = [
                    a.get("normalized_asset") for a in state["assets"]
                ]
                self.db.add_event(
                    job_id,
                    f"Normalized {len(state['assets'])} assets into package manifests",
                    stage="asset_normalization",
                )
                AssetRouter.route_assets(state["assets"])

            self.plugins.run_hook("on_stage_complete", job=job, stage=stage, state=state, output=out)

        # Persist final assets quality scores.
        for a in state["assets"]:
            fp = Path(a.get("file_path", ""))
            if fp.exists():
                self.registry.register(
                    job_id=job_id, role=a.get("role", "unknown"),
                    name=a.get("name", ""), source=a.get("source", ""),
                    file_path=fp, source_url=a.get("source_url"),
                    fmt=a.get("format"), quality_score=a.get("quality_score"),
                    metadata=a.get("metadata", {}), dependencies=a.get("dependencies", []),
                )

        summary = {
            "template": template["id"],
            "asset_count": len(state["assets"]),
            "normalized_asset_count": len(state.get("normalized_assets", [])),
            "normalized_assets": state.get("normalized_assets", []),
            "assets_reused": assets_reused,
            "fbx_path": state.get("fbx_path"),
            "godot_project": state.get("godot_project"),
            "main_scene": state.get("main_scene"),
            "validation": state.get("validation"),
            "deployment_url": results.get("cloud_deploy", {}).get("url"),
            "stages": results,
        }
        manifest = Path(state["jobs_path"]) / "manifest.json"
        manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        
        # Also copy manifest to outputs
        shutil.copy(manifest, Path(state["outputs_path"]) / "manifest.json")
        
        summary["manifest"] = str(manifest)
        self.db.update_job(job_id, progress=1.0)
        return summary
