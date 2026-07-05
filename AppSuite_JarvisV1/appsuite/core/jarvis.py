"""Jarvis Core v1 - Orchestration layer above the existing AppSuite pipeline.

Architecture:
    User Prompt
        -> JarvisCore.run(prompt)
            -> PlanningLayer  (decide what to do)
            -> WorkerCoordinator (execute workers in order)
            -> DecisionLayer (cache checks, retries, routing)
            -> MemoryIntegration (store + learn from outcomes)
        -> JarvisResult

Jarvis does NOT replace existing workers.
It orchestrates them: internet -> analysis -> blender -> godot -> validation.
"""
from __future__ import annotations

import json
import shutil
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .jarvis_brain import ExecutionPlan
from .world_model import WorldModel

from ..db import Database
from ..logging_setup import get_logger

log = get_logger("jarvis.core")



# ─── Data classes ─────────────────────────────────────────────────────────────
@dataclass
class JarvisPlan:
    """Decisions Jarvis makes before touching any worker."""
    prompt: str
    template_id: str
    scene_plan: Dict[str, Any] = field(default_factory=dict)
    use_cached_assets: bool = False
    cached_job_id: Optional[str] = None
    workers_to_run: List[str] = field(default_factory=lambda: [
        "internet", "analysis", "blender", "godot", "validation", "deploy"
    ])
    agent_tasks: List[Any] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class JarvisResult:
    """Final result returned to the caller."""
    job_id: str
    prompt: str
    status: str          # "success" | "failed" | "partial"
    plan: JarvisPlan
    godot_project: Optional[str] = None
    main_scene: Optional[str] = None
    deployment_url: Optional[str] = None
    asset_count: int = 0
    mesh_count: int = 0
    material_count: int = 0
    texture_count: int = 0
    stages: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    resources_at_start: Dict[str, Any] = field(default_factory=dict)
    resources_at_end: Dict[str, Any] = field(default_factory=dict)
    timeline: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "prompt": self.prompt,
            "status": self.status,
            "plan": {
                "template_id": self.plan.template_id,
                "scene_plan": self.plan.scene_plan,
                "use_cached_assets": self.plan.use_cached_assets,
                "cached_job_id": self.plan.cached_job_id,
                "workers_to_run": self.plan.workers_to_run,
                "reasons": self.plan.reasons,
            },
            "godot_project": self.godot_project,
            "main_scene": self.main_scene,
            "deployment_url": self.deployment_url,
            "asset_count": self.asset_count,
            "mesh_count": self.mesh_count,
            "material_count": self.material_count,
            "texture_count": self.texture_count,
            "stages": self.stages,
            "warnings": self.warnings,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
            "resources_at_start": self.resources_at_start,
            "resources_at_end": self.resources_at_end,
            "timeline": self.timeline,
        }


# ─── Jarvis Core v1 ───────────────────────────────────────────────────────────
class JarvisCore:
    """
    Central orchestration layer.

    Existing usage in main.py:
        self.jarvis = JarvisCore(config.scheduler, str(config.abs_path("output_dir")))
        self.jarvis.can_schedule()   <- used by Supervisor

    New usage (CLI / API):
        jarvis.wire(db, registry, memory, templates, workers, pipeline)
        result = jarvis.run("Create a medieval village")
    """

    def __init__(self, config: Dict[str, Any], output_dir: str):
        self.config = config
        self.output_dir = output_dir
        self.start_time = time.time()
        self._last_net = None
        self._last_net_time = None

        # Wired components (populated by wire())
        self._db = None
        self._registry = None
        self._memory = None
        self._templates = None
        self._workers: Dict[str, Any] = {}
        self._pipeline = None
        self._wired = False

    # ── Backward-compatible resource monitoring ──────────────────────────────

    @property
    def uptime(self) -> float:
        return self._hardware.uptime if self._wired else 0.0

    def resources(self) -> Dict[str, Any]:
        return self._hardware.resources() if self._wired else {}

    def can_schedule(self) -> tuple[bool, str]:
        """Used by Supervisor - unchanged from original contract."""
        res      = self.resources()
        cpu_hw   = self.config.get("cpu_high_watermark",    90.0)
        ram_hw   = self.config.get("ram_high_watermark",    90.0)
        disk_low = self.config.get("disk_low_watermark_gb",  1.0)
        if res.get("cpu_percent") is not None and res["cpu_percent"] >= cpu_hw:
            return False, f"CPU at {res['cpu_percent']}% (>= {cpu_hw}%)"
        if res.get("ram_percent") is not None and res["ram_percent"] >= ram_hw:
            return False, f"RAM at {res['ram_percent']}% (>= {ram_hw}%)"
        if res.get("disk", {}).get("free_gb", 100) < disk_low:
            return False, f"Disk free {res['disk']['free_gb']}GB (< {disk_low}GB)"
        return True, "ok"

    def snapshot(self) -> Dict[str, Any]:
        ok, reason = self.can_schedule()
        return {
            "uptime_seconds":      round(self.uptime, 1),
            "resources":           self.resources(),
            "scheduling_allowed":  ok,
            "scheduling_reason":   reason,
        }

    # ── Wiring ───────────────────────────────────────────────────────────────

    def wire(self, db, registry, memory, templates, workers: Dict[str, Any],
             pipeline, brain, hardware, token_banker) -> None:
        """
        Connect Jarvis to the rest of AppSuite.
        Call this once after AppContext builds everything.
        """
        self._db        = db
        self._registry  = registry
        self._memory    = memory
        self._templates = templates
        self._workers   = workers
        self._pipeline  = pipeline
        self._brain     = brain
        self._hardware  = hardware
        self._token_banker = token_banker
        self._coordinator = None  # Will be instantiated later
        self._wired     = True
        log.info("Jarvis wired: %d workers connected", len(workers))

    # ── Planning Layer ────────────────────────────────────────────────────────

    def _plan(self, prompt: str, template_id: Optional[str] = None) -> JarvisPlan:
        """
        Decide what to do before touching any worker.
        Uses the new JarvisBrain ExecutionPlan.
        """
        exec_plan = self._brain.plan_execution(prompt, template_id)
        
        # Resolve template just for logging/reporting backwards compatibility
        template = self._templates.resolve(prompt, template_id) if self._templates else {"id": "generic_scene"}
        resolved_template_id = exec_plan.template_id or template.get("id", "generic_scene")
        scene_plan = exec_plan.metadata.get("scene_plan") or exec_plan.metadata.get("needed_assets") or template.get("scene_plan") or {"needed_assets": []}
        if isinstance(scene_plan, list):
            scene_plan = {"needed_assets": scene_plan}
        
        return JarvisPlan(
            prompt=prompt,
            template_id=resolved_template_id,
            scene_plan=scene_plan,
            use_cached_assets=exec_plan.reused_assets,
            cached_job_id=exec_plan.metadata.get("matched_job"),
            workers_to_run=exec_plan.stages,
            agent_tasks=exec_plan.agent_tasks,
            reasons=[exec_plan.reasoning],
        )

    # ── Decision Layer ────────────────────────────────────────────────────────

    def _should_retry(self, exc: Exception, attempt: int,
                      max_attempts: int) -> bool:
        """Return True if the failure is retryable."""
        if attempt >= max_attempts:
            return False
        msg = str(exc)
        # Non-retryable: bad files, missing binaries
        if any(k in msg for k in (
            "GODOT_NOT_FOUND", "FILE_NOT_FOUND", "TEXTURE_NOT_FOUND",
            "VALIDATION_FAILURE", "BadZipFile",
        )):
            return False
        return True

    # ── Worker Coordinator ────────────────────────────────────────────────────

    def _execute_pipeline(self, job: Dict[str, Any],
                          plan: JarvisPlan) -> Dict[str, Any]:
        """
        Run the existing Pipeline.execute() which already chains all workers.
        Jarvis wraps it for monitoring + retry logic.
        """
        if self._pipeline is None:
            raise RuntimeError("Jarvis not wired — call jarvis.wire() first")

        max_attempts = int(self.config.get("max_attempts", 3))
        backoff      = float(self.config.get("backoff_seconds", 2.0))

        # Attach plan decisions to the job so Pipeline can see them
        job["template_id"]  = plan.template_id
        job["_jarvis_plan"] = plan

        if plan.agent_tasks:
            log.info("[Jarvis] Using Native StateGraph (LangGraph pattern) for dynamic execution, reflection, and replanning.")
            from ..engine.langgraph_agent import StateGraph
            from ..core.project import Project
            from ..engine.job_state import UnifiedJobState
            from ..agents.coordinator import AgentCoordinator
            from ..agents.message_bus import MessageBus

            graph = StateGraph()

            # Define graph nodes
            def initialize_node(state):
                template = self._templates.resolve(state["job"]["prompt"], state["plan"].template_id) if self._templates else {"id": "generic_scene"}
                project = Project(state["job"]["id"], self._pipeline.output_dir)
                project.setup_directories()

                pipeline_state = UnifiedJobState(template=template)
                pipeline_state.update(project.get_state_dict())
                pipeline_state.project = project
                pipeline_state["template"] = template
                pipeline_state.world_model = WorldModel(state["job"]["id"], self._db) if self._db else None

                # Load cached assets if requested
                cached_assets = []
                if state["plan"].use_cached_assets and state["plan"].cached_job_id:
                    prior_assets = self._registry.for_job(state["plan"].cached_job_id) if self._registry else []
                    for a in prior_assets:
                        fp = Path(a.get("file_path", ""))
                        if fp.exists() and fp.stat().st_size > 0:
                            cached_assets.append(dict(a))

                pipeline_state["assets"] = cached_assets
                pipeline_state["normalized_assets"] = []
                pipeline_state["scene_layout"] = {}

                state["pipeline_state"] = pipeline_state
                return state

            def execute_node(state):
                log.info("[Jarvis StateGraph] Executing Node: execute (Attempt %d/%d)", state["attempt"], state["max_attempts"])
                if not self._coordinator:
                    mb = MessageBus()
                    graph_orchestrator = getattr(self._pipeline, 'orchestrator', None)
                    self._coordinator = AgentCoordinator(
                        mb, memory=self._memory, orchestrator=graph_orchestrator,
                        hardware=self._hardware, brain=self._brain, workers=self._workers
                    )

                job_state_dict = {
                    "job": state["job"],
                    "pipeline_state": state["pipeline_state"]
                }

                agent_results = self._coordinator.execute_plan(state["agent_tasks"], job_state_dict)
                state["agent_results"] = agent_results
                state["pipeline_state"] = job_state_dict["pipeline_state"]
                return state

            def reflect_node(state):
                log.info("[Jarvis StateGraph] Executing Node: reflect")
                failed_tasks = [r for r in state["agent_results"] if r.status == "failed"]

                # Human Override / Diagnostic Hook
                if hasattr(self, "on_reasoning_step") and self.on_reasoning_step:
                    try:
                        self.on_reasoning_step({
                            "node": "reflect",
                            "attempt": state["attempt"],
                            "failed_tasks": [t.task_id for t in failed_tasks],
                            "results": [r.__dict__ for r in state["agent_results"]]
                        })
                    except Exception:
                        pass

                if not failed_tasks:
                    state["outcome"] = "success"
                    pstate = state["pipeline_state"]
                    state["result"] = {
                        "status": "success",
                        "godot_project": pstate.get("godot_project"),
                        "main_scene": pstate.get("main_scene"),
                        "deployment_url": pstate.get("deployment_url"),
                        "asset_count": len(pstate.get("assets", [])),
                        "stages": pstate.get("stages", {}),
                        "agent_results": [r.__dict__ for r in state["agent_results"]]
                    }
                else:
                    # Log failures to failure memory (Long-Term Memory Integration)
                    for f in failed_tasks:
                        err_msg = f.output.get("error", "Unknown error")
                        log.warning("[Jarvis StateGraph] Task %s (%s) failed: %s", f.task_id, f.agent_name, err_msg)
                        if hasattr(self._memory, "failure") and hasattr(self._memory.failure, "log_failure"):
                            self._memory.failure.log_failure(
                                state["job"]["prompt"],
                                err_msg,
                                {"task_id": f.task_id, "agent_type": f.agent_name}
                            )

                    # Check if retry or replan is possible
                    if state["attempt"] < state["max_attempts"]:
                        state["outcome"] = "replan"
                    else:
                        state["outcome"] = "failed"
                        first_err = failed_tasks[0].output.get("error", "Unknown agent error")
                        state["error"] = f"Agent {failed_tasks[0].agent_name} failed: {first_err}"
                return state

            def replan_node(state):
                log.info("[Jarvis StateGraph] Executing Node: replan")
                state["attempt"] += 1

                # Gather details of the failures to send back to the planner
                failed_details = []
                for r in state["agent_results"]:
                    if r.status == "failed":
                        failed_details.append(f"Task {r.task_id} ({r.agent_name}) failed with error: {r.output.get('error')}")

                # Call Brain to replan using failure history context
                try:
                    replan_prompt = (
                        f"Prior execution attempt for goal '{state['job']['prompt']}' failed.\n"
                        f"Failures encountered:\n" + "\n".join(failed_details) + "\n"
                        "Generate a corrected execution plan/DAG to fix the failures."
                    )
                    new_exec_plan = self._brain.plan_execution(replan_prompt, getattr(state["plan"], "template_id", None))
                    if new_exec_plan and new_exec_plan.agent_tasks:
                        state["agent_tasks"] = new_exec_plan.agent_tasks
                        state["plan"] = new_exec_plan
                except Exception as e:
                    log.warning("[Jarvis StateGraph] LLM replanning failed: %s. Proceeding with standard retry.", e)

                # Linear backoff before executing again
                wait = backoff * (state["attempt"] - 1)
                log.info("[Jarvis StateGraph] Retrying tasks in %.1fs ...", wait)
                time.sleep(wait)
                return state

            def routing_fn(state):
                return state["outcome"]

            # Wire the graph
            graph.add_node("initialize", initialize_node)
            graph.add_node("execute", execute_node)
            graph.add_node("reflect", reflect_node)
            graph.add_node("replan", replan_node)

            graph.set_entry_point("initialize")
            graph.add_edge("initialize", "execute")
            graph.add_edge("execute", "reflect")
            graph.add_conditional_edges(
                "reflect",
                routing_fn,
                {
                    "success": "__end__",
                    "failed": "__end__",
                    "replan": "replan"
                }
            )
            graph.add_edge("replan", "execute")

            compiled_graph = graph.compile()
            initial_state = {
                "job": job,
                "plan": plan,
                "attempt": 1,
                "max_attempts": max_attempts,
                "agent_tasks": list(plan.agent_tasks),
                "pipeline_state": None,
                "agent_results": [],
                "outcome": None,
                "result": None,
                "error": None,
                "reasons": list(plan.reasons)
            }

            final_state = compiled_graph.invoke(initial_state)

            if final_state["outcome"] == "success":
                return final_state["result"]
            else:
                raise RuntimeError(final_state.get("error", "Graph execution failed"))
        else:
            # Legacy non-graph execution (runs the legacy Pipeline directly)
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    log.info("[Jarvis] Executing legacy pipeline attempt %d/%d for job %s",
                             attempt, max_attempts, job["id"][:8])
                    summary = self._pipeline.execute(job)
                    return summary
                except Exception as exc:
                    last_exc = exc
                    log.warning("[Jarvis] Legacy pipeline attempt %d failed: %s", attempt, exc)
                    if not self._should_retry(exc, attempt, max_attempts):
                        break
                    wait = backoff * attempt
                    log.info("[Jarvis] Retrying in %.1fs ...", wait)
                    time.sleep(wait)
            raise last_exc


    # ── Memory integration ────────────────────────────────────────────────────

    def _remember(self, job_id: str, prompt: str, plan: JarvisPlan,
                  outcome: str, summary: Dict[str, Any]) -> None:
        if self._memory is None:
            return
        enriched = {
            **summary,
            "jarvis_plan": {
                "template_id":       plan.template_id,
                "scene_plan":        plan.scene_plan,
                "use_cached_assets": plan.use_cached_assets,
                "workers_to_run":    plan.workers_to_run,
                "reasons":           plan.reasons,
            },
        }
        try:
            self._memory.remember(job_id, prompt, plan.template_id,
                                  outcome, enriched)
        except Exception as exc:
            log.warning("[Jarvis] Memory store failed: %s", exc)

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self, prompt: str,
            template_id: Optional[str] = None,
            job_id: Optional[str] = None) -> JarvisResult:
        """
        Primary Jarvis interface.

            result = jarvis.run("Create a medieval village")
            print(result.godot_project)

        Parameters
        ----------
        prompt      : Natural-language description of the desired scene.
        template_id : Optional forced template override.
        job_id      : Optional explicit job ID (generated if not given).

        Returns
        -------
        JarvisResult with full details of what happened.
        """
        if not self._wired:
            raise RuntimeError(
                "Jarvis is not wired. Call jarvis.wire(db, registry, memory, "
                "templates, workers, pipeline) before jarvis.run()."
            )

        job_id    = job_id or str(uuid.uuid4())
        t_start   = time.time()
        res_start = self.resources()

        log.info("[Jarvis] *** START job=%s prompt=%r ***", job_id[:8], prompt[:80])

        # ── 1. Planning ───────────────────────────────────────────────────────
        plan = self._plan(prompt, template_id)
        log.info("[Jarvis] Plan: template=%s cached=%s workers=%s",
                 plan.template_id, plan.use_cached_assets, plan.workers_to_run)
        for r in plan.reasons:
            log.info("[Jarvis]   reason: %s", r)

        # ── 2. Resource gate ──────────────────────────────────────────────────
        ok, gate_reason = self.can_schedule()
        warnings: List[str] = []
        if not ok:
            warnings.append(f"Resource gate: {gate_reason} — proceeding anyway")
            log.warning("[Jarvis] Resource gate warn: %s", gate_reason)

        # ── 3. DB job creation ────────────────────────────────────────────────
        if self._db is not None:
            self._db.create_job(job_id, prompt, plan.template_id)
            self._db.add_event(job_id, f"Jarvis plan: {json.dumps(plan.reasons)}",
                               stage="planning")
            log.info("[Jarvis] DB job created: %s", job_id)

        # ── 4. Execute pipeline ───────────────────────────────────────────────
        job = {"id": job_id, "prompt": prompt, "template_id": plan.template_id}
        errors: List[str] = []
        summary: Dict[str, Any] = {}
        status = "failed"

        try:
            summary = self._execute_pipeline(job, plan)
            status  = "success"
            log.info("[Jarvis] Pipeline SUCCESS for job %s", job_id[:8])
            if self._db is not None:
                self._db.update_job(job_id, status="completed", stage="done",
                                    result_json=json.dumps(summary), error=None)
                self._db.add_event(job_id, "Jarvis: pipeline completed", stage="done")
        except Exception as exc:
            tb = traceback.format_exc()
            errors.append(str(exc))
            log.error("[Jarvis] Pipeline FAILED for job %s: %s", job_id[:8], exc)
            if self._db is not None:
                self._db.update_job(job_id, status="failed", stage="error",
                                    error=str(exc))
                self._db.add_event(job_id, f"Jarvis: pipeline failed: {exc}",
                                   stage="error", level="error")

        # ── 5. Memory ────────────────────────────────────────────────────────
        self._remember(job_id, prompt, plan, status, summary)

        # ── 6. Build result ───────────────────────────────────────────────────
        val   = summary.get("validation", {})
        diags = {}
        mesh_count = material_count = texture_count = 0
        if isinstance(val, dict):
            for chk in val.get("checks", []):
                name = chk.get("name", "")
                if "mesh" in name and isinstance(chk.get("detail"), int):
                    mesh_count = chk["detail"]
                if "material" in name and isinstance(chk.get("detail"), int):
                    material_count = chk["detail"]
                if "texture" in name and isinstance(chk.get("detail"), int):
                    texture_count = chk["detail"]
        # Fallback: derive from godot stage output if validation didn't expose counts
        stages = summary.get("stages", {}) or {}
        godot_out = stages.get("godot_import", {}) or {}
        if not texture_count:
            texture_count = int(godot_out.get("import_files", 0) or 0)
        if not mesh_count:
            mesh_count = int(godot_out.get("assets_imported", 0) or 0)

        result = JarvisResult(
            job_id     = job_id,
            prompt     = prompt,
            status     = status,
            plan       = plan,
            godot_project = summary.get("godot_project"),
            main_scene    = summary.get("main_scene"),
            deployment_url = summary.get("deployment_url"),
            asset_count   = summary.get("asset_count", 0),
            mesh_count    = mesh_count,
            material_count = material_count,
            texture_count = texture_count,
            stages        = summary.get("stages", {}),
            warnings      = warnings,
            errors        = errors,
            duration_seconds = time.time() - t_start,
            resources_at_start = res_start,
            resources_at_end   = self.resources(),
            timeline           = self._db.get_job_timeline(job_id) if self._db else [],
        )

        # Print final summary with deployment URL
        log.info("[Jarvis] *** END job=%s status=%s duration=%.1fs ***",
                 job_id[:8], status, result.duration_seconds)
        if result.timeline:
            log.info("[Jarvis] --- Timeline ---")
            for line in result.timeline:
                log.info("[Jarvis]   %s", line)
        
        if result.deployment_url:
            log.info("[Jarvis] *** LIVE URL: %s ***", result.deployment_url)
        return result

    # ── Status helper ─────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of Jarvis state (used by API routes)."""
        return {
            **self.snapshot(),
            "wired":          self._wired,
            "workers_wired":  list(self._workers.keys()),
            "pipeline_ready": self._pipeline is not None,
        }
