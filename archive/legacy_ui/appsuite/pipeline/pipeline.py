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
from ..core.state import WorkerStatus, WorkerResult
from ..engine.job_state import UnifiedJobState as JobState

log = get_logger("pipeline")


class Pipeline:
    def __init__(self, db, registry, memory, templates, plugins, workers: Dict[str, Any],
                 output_dir: Path, orchestrator_mode: str = "graph"):
        self.db = db
        self.registry = registry
        self.memory = memory
        self.templates = templates
        self.plugins = plugins
        self.workers = workers
        self.output_dir = Path(output_dir)
        self.orchestrator_mode = orchestrator_mode
        self.supervisor = None  # Will be wired later or passed in
        # Ordered pipeline stages: (stage_label, worker_key).
        self.stages: List[Tuple[str, str]] = [
            ("asset_search", "internet"),
            ("asset_processing", "analysis"),
            ("blender_import", "blender"),
            ("godot_import", "godot"),
            ("output_validation", "validation"),
            ("cloud_deploy", "deploy"),
        ]
        
        self.orchestrator = None
        if self.orchestrator_mode == "graph":
            from ..engine.orchestrator import GraphOrchestrator
            
            # Local legacy wrappers for backward compatibility with orchestrator.run()
            class LegacyNode:
                def __init__(self, name: str, worker: Any):
                    self.name = name
                    self.worker = worker
                def process(self, state: Any) -> Any:
                    from ..core.health import WorkerHealthMonitor
                    worker_type = self.name.split('_')[0]
                    is_healthy, h_reason = WorkerHealthMonitor.preflight_check(worker_type)
                    if not is_healthy:
                        result = WorkerResult(status=WorkerStatus.FAILED, reason=h_reason)
                    else:
                        if hasattr(self.worker, "process"):
                            result = self.worker.process(state.job, state.pipeline_state)
                        else:
                            result = self.worker.run(state.job, state.pipeline_state)
                    state.worker_result = result
                    state.current_node = self.name
                    state.history.append(self.name)
                    return state

            class LegacyParallelInternetNode(LegacyNode):
                def process(self, state: Any) -> Any:
                    import time
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    from pathlib import Path
                    
                    t0 = time.time()
                    try:
                        template = state.pipeline_state.get("template", {})
                        job_id = state.job["id"]
                        tasks = []
                        seen_tasks = set()
                        for slot in template.get("asset_slots", []):
                            role = slot["role"]
                            terms = slot.get("search_terms", [role])
                            count = slot.get("count", 1)
                            for i in range(count):
                                term = terms[i % len(terms)]
                                if (role, term) not in seen_tasks:
                                    seen_tasks.add((role, term))
                                    tasks.append((role, term))
                                
                        assets = []
                        cache_hits = 0
                        real_downloads = 0
                        
                        def fetch_with_retry(job_id, role, term):
                            last_err = None
                            for attempt in range(3):
                                try:
                                    asset = self.worker.search_and_fetch(job_id, role, term)
                                    if "file_path" in asset and asset["file_path"]:
                                        fpath = Path(asset["file_path"])
                                        if fpath.exists():
                                            if fpath.stat().st_size == 0:
                                                fpath.unlink()
                                                raise ValueError(f"Corrupted 0-byte file downloaded for {role}")
                                    return asset
                                except Exception as e:
                                    last_err = e
                                    time.sleep(1)
                            raise last_err
                        
                        max_workers = getattr(self.worker, 'config', {}).get('max_concurrent_downloads', 5)
                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            future_to_task = {
                                executor.submit(fetch_with_retry, job_id, role, term): (role, term)
                                for role, term in tasks
                            }
                            for future in as_completed(future_to_task):
                                role, term = future_to_task[future]
                                try:
                                    asset = future.result()
                                    assets.append(asset)
                                    if asset.get("cache_hit"):
                                        cache_hits += 1
                                    if asset.get("source") in ("kenney", "poly_pizza"):
                                        real_downloads += 1
                                except Exception as e:
                                    raise e
                        
                        state.pipeline_state["assets"] = assets
                        result = WorkerResult(
                            status=WorkerStatus.SUCCESS,
                            data={
                                "assets_fetched": len(assets),
                                "cache_hits": cache_hits,
                                "real_downloads": real_downloads
                            },
                            reason="",
                            metadata={"assets_created": len(assets)}
                        )
                    except Exception as e:
                        result = WorkerResult(
                            status=WorkerStatus.FAILED,
                            reason=str(e),
                            metadata={"error_type": type(e).__name__}
                        )
                    
                    result.metadata["execution_time"] = time.time() - t0
                    state.worker_result = result
                    state.current_node = self.name
                    state.history.append(self.name)
                    return state

            self.orchestrator = GraphOrchestrator(self.db)
            if "internet" in self.workers:
                self.orchestrator.add_node("asset_search", LegacyParallelInternetNode("asset_search", self.workers["internet"]))
            if "analysis" in self.workers:
                self.orchestrator.add_node("asset_processing", LegacyNode("asset_processing", self.workers["analysis"]))
            if "blender" in self.workers:
                self.orchestrator.add_node("blender_import", LegacyNode("blender_import", self.workers["blender"]))
            if "godot" in self.workers:
                self.orchestrator.add_node("godot_import", LegacyNode("godot_import", self.workers["godot"]))
            if "validation" in self.workers:
                self.orchestrator.add_node("output_validation", LegacyNode("output_validation", self.workers["validation"]))
            if "deploy" in self.workers:
                self.orchestrator.add_node("cloud_deploy", LegacyNode("cloud_deploy", self.workers["deploy"]))

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

        state = JobState(template=template, job=job)
        state.update(project.get_state_dict())
        state.project = project

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

        results: Dict[str, Any] = {}
        
        if self.orchestrator_mode == "graph":
            from ..core.supervisor import SupervisorAction
            
            class DecisionNode:
                def __init__(self, supervisor):
                    self.supervisor = supervisor
                def route(self, state) -> str:
                    if not state.worker_result:
                        return "END"
                    job_id = state.job["id"]
                    stage_name = state.current_node
                    action = self.supervisor.handle_result(job_id, stage_name, state.worker_result)
                    if action == SupervisorAction.ABORT:
                        return "ABORT"
                    if state.worker_result and state.worker_result.status.name == "NEED_ASSET":
                        return "asset_search"
                    if action in (SupervisorAction.RETRY, SupervisorAction.CHANGE_PROVIDER):
                        return stage_name
                    elif action == SupervisorAction.PROCEED:
                        if stage_name == "asset_search":
                            return "asset_processing"
                        elif stage_name == "asset_processing":
                            return "blender_import"
                        elif stage_name == "blender_import":
                            return "godot_import"
                        elif stage_name == "godot_import":
                            return "output_validation"
                        elif stage_name == "output_validation":
                            return "cloud_deploy"
                        elif stage_name == "cloud_deploy":
                            return "END"
                    return "END"
            
            graph = self.orchestrator
            
            # Setup router
            if self.supervisor:
                graph.set_router(DecisionNode(self.supervisor))
            
            # Start node depends on memory
            if assets_reused:
                graph._start_node = "asset_processing"
                
            job_state = {"job": job, "pipeline_state": state}
            
            # Execute dynamic graph!
            completed_state = graph.run(job_state)
            
            return {
                "job_id": job_id,
                "template": template["id"],
                "assets_reused": assets_reused,
                "stages": completed_state.get("stages", {}),
                "history": completed_state.get("history", []),
                "failure_reason": completed_state.get("failure_reason", "")
            }
        
        # Define stage progression mapping
        TRANSITIONS = {
            "asset_search": {
                WorkerStatus.SUCCESS: "asset_processing",
                WorkerStatus.NEED_RETRY: "asset_search"
            },
            "asset_processing": {
                WorkerStatus.SUCCESS: "blender_import"
            },
            "blender_import": {
                WorkerStatus.SUCCESS: "godot_import",
                WorkerStatus.NEED_ASSET: "asset_search",
                WorkerStatus.NEED_RETRY: "blender_import"
            },
            "godot_import": {
                WorkerStatus.SUCCESS: "output_validation",
                WorkerStatus.NEED_ASSET: "blender_import",
                WorkerStatus.NEED_RETRY: "godot_import"
            },
            "output_validation": {
                WorkerStatus.SUCCESS: "cloud_deploy",
                WorkerStatus.NEED_RETRY: "godot_import"
            },
            "cloud_deploy": {
                WorkerStatus.SUCCESS: "end"
            }
        }
        
        WORKER_MAP = {
            "asset_search": "internet",
            "asset_processing": "analysis",
            "blender_import": "blender",
            "godot_import": "godot",
            "output_validation": "validation",
            "cloud_deploy": "deploy"
        }
        
        # Seed current_stage from the ExecutionPlan provided by JarvisBrain
        plan = job.get("_jarvis_plan")
        if plan and getattr(plan, "workers_to_run", None) and plan.workers_to_run:
            current_stage = plan.workers_to_run[0]
            # Log skipping if we bypassed asset_search
            if current_stage != "asset_search":
                results["asset_search"] = {"assets_fetched": len(state.assets), "reused": True}
                self.db.add_event(job_id, f"Skipping up to {current_stage}: brain execution plan override", stage="asset_search")
        else:
            current_stage = "asset_processing" if assets_reused else "asset_search"
            if assets_reused:
                results["asset_search"] = {"assets_fetched": len(state.assets), "reused": True}
                self.db.add_event(job_id, "Skipped asset_search: reusing prior assets", stage="asset_search")

        max_steps = 20
        steps = 0
        while current_stage != "end":
            steps += 1
            if steps > max_steps:
                raise RuntimeError(f"Pipeline exceeded max steps ({max_steps}) at stage {current_stage}")
                
            worker_key = WORKER_MAP.get(current_stage)
            if not worker_key:
                break
                
            worker = self.workers[worker_key]
            self.db.update_job(job_id, stage=current_stage)
            self.db.add_event(job_id, f"Stage start: {current_stage}", stage=current_stage)
            log.info("[%s] stage %s started", job_id, current_stage)

            t0 = time.monotonic()
            try:
                result = worker.run(job, state)
            except Exception as e:
                log.error("[%s] Worker %s crashed: %s", job_id, current_stage, e)
                result = WorkerResult(status=WorkerStatus.FAILED, reason=str(e))

            status = result.status
            out = result.data
            duration = time.monotonic() - t0
            
            # Auto-inject execution metadata to fulfill Phase 3 self-reporting requirement
            if "execution_time" not in result.metadata:
                result.metadata["execution_time"] = duration
            out["_metadata"] = result.metadata

            results[current_stage] = out
            log.info("[%s] stage %s completed in %.3fs with status %s", job_id, current_stage, duration, status.name)
            self.db.add_event(
                job_id,
                f"Stage done: {current_stage} in {duration:.3f}s status={status.name} -> {json.dumps(out)[:300]}",
                stage=current_stage,
            )

            # ── Phase 4: Supervisor Intervention ──
            if self.supervisor:
                action = self.supervisor.handle_result(job_id, current_stage, result)
                if action.value == "retry":
                    self.db.add_event(job_id, f"Supervisor ordered RETRY for {current_stage}", stage=current_stage)
                    continue
                elif action.value == "skip":
                    self.db.add_event(job_id, f"Supervisor ordered SKIP for {current_stage}", stage=current_stage)
                    # For skip, we just rely on TRANSITIONS.get(current_stage).get(SUCCESS) to find the next stage usually
                    # But since it failed, let's just force success transition path to find next_stage
                    next_stage = TRANSITIONS.get(current_stage, {}).get(WorkerStatus.SUCCESS)
                    if next_stage:
                        current_stage = next_stage
                        continue
                    else:
                        raise RuntimeError(f"Supervisor ordered SKIP but no SUCCESS transition for {current_stage}")
                elif action.value == "abort":
                    reason = result.reason or str(out)
                    raise RuntimeError(f"Supervisor aborted job at stage {current_stage}: {reason}")
                elif action.value == "change_provider":
                    self.db.add_event(job_id, f"Supervisor ordered CHANGE_PROVIDER for {current_stage}", stage=current_stage)
                    continue
                # PROCEED drops through to standard logic below

            next_stage = TRANSITIONS.get(current_stage, {}).get(status)
            if not next_stage:
                # If supervisor proceeded but there's no transition, it's a hard error unless we are at the end
                raise RuntimeError(f"No transition defined for stage {current_stage} with status {status.name}")

            if status == WorkerStatus.SUCCESS:
                # Route assets if they were just fetched
                if current_stage == "asset_search":
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

                self.plugins.run_hook("on_stage_complete", job=job, stage=current_stage, state=state, output=out)
                current_stage = next_stage
                
            elif status == WorkerStatus.NEED_ASSET:
                self.db.add_event(job_id, "Routing back to asset_search due to missing assets", stage=current_stage)
                current_stage = next_stage
                
            elif status == WorkerStatus.NEED_RETRY:
                # Fallback if supervisor not wired
                self.db.add_event(job_id, f"Retrying current stage {current_stage}", stage=current_stage)
                current_stage = next_stage
            
            else:
                current_stage = next_stage

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
