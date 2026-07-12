"""
Supervisor V2 Intelligence Layer
=================================
Adds planning, risk estimation, failure prediction, and reasoning logs
to the Supervisor before every job dispatch.

All methods are stateless and safe to call from any thread.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..logging_setup import get_logger
from .debate_room import DebateRoom

log = get_logger("supervisor.intelligence")

# ---------------------------------------------------------------------------
# Known dependency checks (static heuristics)
# ---------------------------------------------------------------------------

_GODOT_STAGES   = {"godot_import", "godot_scene", "godot"}
_BLENDER_STAGES = {"blender_import", "blender_process", "blender"}
_NET_STAGES     = {"asset_search", "internet", "download"}

_WORKER_BASE_RELIABILITY: Dict[str, float] = {
    "internet":   0.93,
    "analysis":   0.97,
    "blender":    0.72,   # binary dependency - lower base
    "godot":      0.81,   # binary dependency
    "validation": 0.95,
    "deploy":     0.88,
    "code":       0.90,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlanningContext:
    prompt: str
    similar_successes: List[Dict[str, Any]] = field(default_factory=list)
    common_failures:   List[Dict[str, Any]] = field(default_factory=list)
    recommended_strategy: Optional[Dict[str, Any]] = None
    best_assets:       Dict[str, str]        = field(default_factory=dict)
    reliability_score: float                 = 1.0
    predicted_risks:   List[str]             = field(default_factory=list)
    reasoning:         str                   = ""


@dataclass
class ExecutionPlan:
    prompt: str
    template_id: str
    worker_sequence: List[str]
    asset_hints: Dict[str, str]       # category -> preferred asset name
    success_probability: float
    risk_flags: List[str]
    reasoning: str
    planning_context: Optional[PlanningContext] = None


# ---------------------------------------------------------------------------
# Core intelligence class
# ---------------------------------------------------------------------------

class SupervisorIntelligence:
    """
    Plugs into Supervisor._tick() just before dispatch.
    Reads from JarvisMemory, computes a plan, emits reasoning to timeline.
    """

    # Default worker sequence when no history available
    _DEFAULT_SEQUENCE = ["internet", "analysis", "godot", "validation"]

    def __init__(self, db, jarvis_memory) -> None:
        self.db = db
        self.memory = jarvis_memory
        self.debate_room = DebateRoom(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_execution_plan(self, prompt: str, job_id: str) -> ExecutionPlan:
        """Full planning cycle. Returns an ExecutionPlan ready for dispatch."""
        ctx = self._build_planning_context(prompt)
        risks = self.predict_failures(prompt, ctx)
        
        # Hold debate to get best strategy
        winning_proposal = self.debate_room.hold_debate(prompt, ctx, risks, job_id)
        
        workers = winning_proposal.worker_sequence
        assets = winning_proposal.asset_hints
        template = winning_proposal.template_id
        
        prob = self.estimate_success_probability(prompt, ctx, workers)
        reasoning = self._build_reasoning(prompt, ctx, prob, risks)
        reasoning += f" | Debate Winner: {winning_proposal.agent_name} -> {winning_proposal.reasoning}"

        plan = ExecutionPlan(
            prompt=prompt,
            template_id=template,
            worker_sequence=workers,
            asset_hints=assets,
            success_probability=prob,
            risk_flags=risks,
            reasoning=reasoning,
            planning_context=ctx,
        )

        log.info("[%s] Plan: template=%s  p=%.2f  risks=%d",
                 job_id[:8], template, prob, len(risks))
        log.info("[%s] Reasoning: %s", job_id[:8], reasoning[:200])
        return plan

    def estimate_success_probability(
        self, prompt: str, ctx: Optional[PlanningContext] = None, workers: Optional[List[str]] = None
    ) -> float:
        """
        Returns 0.0–1.0 composite probability based on:
        - Prior similar-success rate
        - Worker reliability for required workers
        - Asset success rates
        - Known failure density for this prompt type
        """
        if ctx is None:
            ctx = self._build_planning_context(prompt)

        score = 0.75  # neutral baseline

        # Factor 1: prior similar success boosts confidence
        if ctx.similar_successes:
            best = ctx.similar_successes[0]
            sim = best.get("similarity_score", 0.5)
            rel = best.get("reliability_score", 1.0)
            score += 0.15 * sim * rel

        # Factor 2: known failures reduce confidence
        failure_penalty = min(0.30, len(ctx.common_failures) * 0.05)
        score -= failure_penalty

        # Factor 3: worker reliability for recommended sequence
        worker_names = workers or self.recommend_workers(prompt, ctx)
        if worker_names:
            avg_worker_rel = sum(
                _WORKER_BASE_RELIABILITY.get(w, 0.85) for w in worker_names
            ) / len(worker_names)
            score = score * 0.6 + avg_worker_rel * 0.4

        # Factor 4: recurring failures in memory
        recurring = self.memory.failure.get_recurring(min_count=2)
        if recurring:
            score -= min(0.10, len(recurring) * 0.02)

        return round(max(0.05, min(0.99, score)), 3)

    def predict_failures(
        self, prompt: str, ctx: Optional[PlanningContext] = None
    ) -> List[str]:
        """
        Returns list of predicted risk strings.
        Checks: missing deps, import failures, asset issues, worker crashes.
        """
        if ctx is None:
            ctx = self._build_planning_context(prompt)

        risks: List[str] = []

        # --- Dependency checks (heuristic from prompt keywords) ---
        pl = prompt.lower()
        if any(k in pl for k in ("3d", "model", "mesh", "blender", "fbx", "glb")):
            blender_rel = _WORKER_BASE_RELIABILITY["blender"]
            if blender_rel < 0.80:
                risks.append("BLENDER_NOT_FOUND: binary dependency may be missing")

        if any(k in pl for k in ("godot", "scene", "game", "fps", "rpg", "street")):
            risks.append("GODOT_IMPORT: scene assembly may fail if .tscn path is invalid")

        if any(k in pl for k in ("download", "internet", "asset", "fetch", "url")):
            risks.append("NETWORK_TIMEOUT: asset download may time out on slow connections")

        # --- Asset failure patterns from memory ---
        asset_rows = self.memory.asset.get_all()
        for a in asset_rows:
            sr = a.get("success_rate", 1.0) or 1.0
            if sr < 0.50 and a.get("use_count", 0) >= 3:
                risks.append(
                    f"ASSET_UNRELIABLE: {a['asset_name']} has {sr*100:.0f}% success rate"
                )

        # --- Known failures for similar prompts ---
        for f in ctx.common_failures[:3]:
            err = f.get("error", "")
            if err and err not in [r.split(":")[0] for r in risks]:
                risks.append(f"KNOWN_FAILURE: {err[:80]}")

        # --- Recurring system failures ---
        recurring = self.memory.failure.get_recurring(min_count=3)
        for r in recurring[:2]:
            risks.append(f"RECURRING_ERROR({r['count']}x): {r['error'][:60]}")

        return risks

    def recommend_assets(
        self, prompt: str, ctx: Optional[PlanningContext] = None
    ) -> Dict[str, str]:
        """Returns category -> best_asset_name mapping."""
        if ctx is None:
            ctx = self._build_planning_context(prompt)

        hints: Dict[str, str] = {}

        # From prior success reuse
        if ctx.similar_successes:
            best = ctx.similar_successes[0]
            for entry in best.get("assets_used", []):
                parts = str(entry).split(":")
                if len(parts) >= 3:
                    name, _src, cat = parts[0], parts[1], parts[2]
                    hints.setdefault(cat, name)

        # From asset memory best-performers per category
        roles = self._infer_roles_from_prompt(prompt)
        for role in roles:
            best_name = self.memory.get_best_asset(role)
            if best_name:
                hints.setdefault(role, best_name)

        return hints

    def recommend_workers(
        self, prompt: str, ctx: Optional[PlanningContext] = None
    ) -> List[str]:
        """Returns ordered worker sequence for this prompt."""
        if ctx is None:
            ctx = self._build_planning_context(prompt)

        # Use strategy memory if available
        if ctx.recommended_strategy:
            combo = ctx.recommended_strategy.get("strategy", {}).get("worker_combination")
            if combo:
                return combo

        # Heuristic from prompt keywords
        pl = prompt.lower()
        workers = ["internet", "analysis"]
        if any(k in pl for k in ("3d", "model", "mesh", "blender", "fbx")):
            workers.append("blender")
        workers.append("godot")
        workers.append("validation")
        return workers

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_planning_context(self, prompt: str) -> PlanningContext:
        ctx = PlanningContext(prompt=prompt)
        try:
            prior = self.memory.success.find_similar(prompt, threshold=0.30)
            if prior:
                ctx.similar_successes = [prior]
            ctx.common_failures = self.memory.failure.get_common_failures(prompt, limit=5)
            ctx.recommended_strategy = self.memory.strategy.get_best(prompt, threshold=0.30)
            # Preferred assets per inferred role
            for role in self._infer_roles_from_prompt(prompt):
                best = self.memory.get_best_asset(role)
                if best:
                    ctx.best_assets[role] = best
            # Reliability from prior success
            if ctx.similar_successes:
                ctx.reliability_score = ctx.similar_successes[0].get("reliability_score", 1.0)
        except Exception as exc:
            log.warning("PlanningContext build error: %s", exc)
        return ctx

    def _pick_template(self, ctx: PlanningContext) -> str:
        # Prefer template from best prior success
        if ctx.similar_successes:
            return ctx.similar_successes[0].get("template_id", "generic_scene")
        if ctx.recommended_strategy:
            return ctx.recommended_strategy.get("strategy", {}).get("template_id", "generic_scene")
        return "generic_scene"

    def _infer_roles_from_prompt(self, prompt: str) -> List[str]:
        pl = prompt.lower()
        roles = []
        if any(k in pl for k in ("npc", "character", "person", "enemy")):
            roles.append("npc")
        if any(k in pl for k in ("house", "building", "city", "urban", "street")):
            roles.append("house")
        if any(k in pl for k in ("tree", "nature", "forest", "plant")):
            roles.append("tree")
        if any(k in pl for k in ("road", "street", "path")):
            roles.append("road")
        if any(k in pl for k in ("prop", "object", "item")):
            roles.append("prop")
        return roles or ["prop"]

    def _build_reasoning(
        self,
        prompt: str,
        ctx: PlanningContext,
        prob: float,
        risks: List[str],
    ) -> str:
        lines: List[str] = []

        if ctx.similar_successes:
            s = ctx.similar_successes[0]
            sim = s.get("similarity_score", 0)
            lines.append(
                f"Found similar prior job (similarity={sim:.0%}, "
                f"template={s.get('template_id')}, "
                f"reliability={s.get('reliability_score', 1.0):.0%})."
            )
        else:
            lines.append("No similar prior jobs found – using default strategy.")

        if ctx.recommended_strategy:
            combo = ctx.recommended_strategy.get("strategy", {}).get("worker_combination", [])
            lines.append(f"Best known worker combination: {', '.join(combo) or 'default'}.")

        if ctx.best_assets:
            asset_str = ", ".join(f"{k}={v}" for k, v in list(ctx.best_assets.items())[:3])
            lines.append(f"Preferred assets from memory: {asset_str}.")

        if ctx.common_failures:
            lines.append(
                f"{len(ctx.common_failures)} known failure pattern(s) for similar prompts."
            )

        if risks:
            lines.append(f"Predicted risks: {'; '.join(risks[:3])}.")

        lines.append(f"Estimated success probability: {prob:.0%}.")
        return " ".join(lines)
