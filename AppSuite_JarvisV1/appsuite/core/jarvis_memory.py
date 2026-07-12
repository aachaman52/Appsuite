"""
Jarvis Memory System
====================
Unified memory facade that Jarvis consults BEFORE every planning cycle and
updates AFTER every execution cycle.

Sub-systems
-----------
  SuccessMemory   – rich record of what worked (template, workers, assets, timing)
  FailureMemory   – what failed, why, and what fixed it
  AssetMemory     – per-asset success/fail rates and import issues
  StrategyMemory  – high-level planning patterns per prompt category

Retrieval APIs
--------------
  find_similar_prompt(prompt)   -> best prior success record or None
  get_best_strategy(prompt)     -> best known strategy dict or None
  get_best_asset(category)      -> best-performing asset name for a category or None
  get_common_failures(prompt)   -> list of known failure contexts to avoid
"""
from __future__ import annotations

import difflib
import json
import time
import traceback
from typing import Any, Dict, List, Optional

from ..db import Database
from ..logging_setup import get_logger

log = get_logger("jarvis.memory")


# ---------------------------------------------------------------------------
# Success Memory
# ---------------------------------------------------------------------------

class SuccessMemory:
    """Stores rich details of every successful job execution."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        job_id: str,
        prompt: str,
        template_id: str,
        workers_used: List[str],
        assets_used: List[str],
        completion_time_secs: float,
        generated_files: List[str],
        reliability_score: float = 1.0,
    ) -> None:
        try:
            self.db.add_success_memory(
                job_id=job_id,
                prompt=prompt,
                template_id=template_id,
                workers_used=workers_used,
                assets_used=assets_used,
                completion_time_secs=completion_time_secs,
                generated_files=generated_files,
                reliability_score=reliability_score,
            )
            log.info("SuccessMemory: recorded job %s (template=%s)", job_id[:8], template_id)
        except Exception as exc:
            log.warning("SuccessMemory: failed to record job %s – %s", job_id[:8], exc)

    def find_similar(self, prompt: str, threshold: float = 0.45) -> Optional[Dict[str, Any]]:
        """Find the most similar prior success using keyword + difflib similarity."""
        candidates = self.db.find_similar_success(prompt, limit=10)
        if not candidates:
            return None

        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for row in candidates:
            score = difflib.SequenceMatcher(None, prompt.lower(), row["prompt"].lower()).ratio()
            if score > best_score:
                best_score = score
                best = row

        if best and best_score >= threshold:
            best["similarity_score"] = best_score
            return best
        return None

    def get_top_templates(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns template_ids ranked by reliability score."""
        rows = self.db.query(
            "SELECT template_id, AVG(reliability_score) AS avg_score, COUNT(*) AS uses "
            "FROM success_memory GROUP BY template_id ORDER BY avg_score DESC LIMIT ?",
            (limit,)
        )
        return rows


# ---------------------------------------------------------------------------
# Failure Memory
# ---------------------------------------------------------------------------

class FailureMemory:
    """Stores failure context, root cause, and repair actions."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        prompt: str,
        worker: str,
        stage: str,
        error: str,
        stacktrace: str = "",
        fix_that_worked: str = "",
        retry_count: int = 0,
    ) -> None:
        ctx = {
            "worker": worker,
            "stage": stage,
            "stacktrace": stacktrace[-2000:],
            "fix_that_worked": fix_that_worked,
            "retry_count": retry_count,
        }
        try:
            self.db.add_failure_memory(prompt, error, ctx)
            log.info("FailureMemory: recorded failure [%s] at stage %s", error[:60], stage)
        except Exception as exc:
            log.warning("FailureMemory: failed to record – %s", exc)

    def get_common_failures(self, prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns failure records similar to the given prompt."""
        # Exact-match first
        rows = self.db.get_failure_memories(prompt, limit=limit)
        if rows:
            return rows
        # Keyword fallback
        words = [w for w in prompt.split() if len(w) > 3]
        if not words:
            return []
        conditions = " OR ".join(["lower(prompt) LIKE ?" for _ in words])
        params = tuple(f"%{w.lower()}%" for w in words) + (limit,)
        rows = self.db.query(
            f"SELECT * FROM failure_memory WHERE {conditions} "
            f"ORDER BY created_at DESC LIMIT ?",
            params
        )
        for r in rows:
            if r.get("context_json") and "context" not in r:
                try:
                    r["context"] = json.loads(r["context_json"])
                except Exception:
                    r["context"] = {}
        return rows

    def get_recurring(self, min_count: int = 2) -> List[Dict[str, Any]]:
        """Returns errors that have been seen >= min_count times."""
        return self.db.query(
            "SELECT error, COUNT(*) AS count, MAX(created_at) AS last_seen "
            "FROM failure_memory GROUP BY error HAVING count >= ? ORDER BY count DESC",
            (min_count,)
        )


# ---------------------------------------------------------------------------
# Asset Memory
# ---------------------------------------------------------------------------

class AssetMemory:
    """Tracks per-asset usage, success rates, and import issues."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record_usage(
        self,
        asset_name: str,
        asset_source: str,
        category: str,
        success: bool,
        import_issue: Optional[str] = None,
    ) -> None:
        try:
            self.db.record_asset_usage(asset_name, asset_source, category, success, import_issue)
        except Exception as exc:
            log.warning("AssetMemory: failed to record usage – %s", exc)

    def get_best_for_category(self, category: str) -> Optional[str]:
        """Returns the asset_name with the highest success rate for a category."""
        rows = self.db.get_best_assets_for_category(category, limit=1)
        if rows:
            return rows[0]["asset_name"]
        return None

    def get_preferred_assets(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.db.get_best_assets_for_category(category, limit=limit)

    def get_all(self) -> List[Dict[str, Any]]:
        return self.db.get_all_asset_memory()

    def get_known_issues(self, asset_name: str) -> List[str]:
        """Returns known import issues for a specific asset."""
        row = self.db.query_one(
            "SELECT import_issues_json FROM asset_memory WHERE asset_name=?",
            (asset_name,)
        )
        if row and row.get("import_issues_json"):
            try:
                return json.loads(row["import_issues_json"])
            except Exception:
                pass
        return []


# ---------------------------------------------------------------------------
# Strategy Memory
# ---------------------------------------------------------------------------

class StrategyMemory:
    """Stores and retrieves successful planning strategies per prompt category."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        prompt: str,
        template_id: str,
        worker_combination: List[str],
        repair_strategy: str = "",
        outcome: str = "success",
    ) -> None:
        strategy = {
            "template_id": template_id,
            "worker_combination": worker_combination,
            "repair_strategy": repair_strategy,
        }
        try:
            self.db.add_strategy_memory(prompt, strategy, outcome)
            log.info("StrategyMemory: recorded strategy for prompt '%s...'", prompt[:40])
        except Exception as exc:
            log.warning("StrategyMemory: failed to record – %s", exc)

    def get_best(self, prompt: str, threshold: float = 0.40) -> Optional[Dict[str, Any]]:
        """Returns the highest-scoring strategy for a similar prompt."""
        # Pull all successful strategies
        rows = self.db.query(
            "SELECT * FROM strategy_memory WHERE outcome='success' ORDER BY created_at DESC LIMIT 100"
        )
        if not rows:
            return None

        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for row in rows:
            score = difflib.SequenceMatcher(None, prompt.lower(), row["prompt"].lower()).ratio()
            if score > best_score:
                best_score = score
                best = row

        if best and best_score >= threshold:
            if best.get("strategy_json") and "strategy" not in best:
                try:
                    best["strategy"] = json.loads(best["strategy_json"])
                except Exception:
                    best["strategy"] = {}
            best["similarity_score"] = best_score
            return best
        return None

    def get_top_worker_combinations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns most commonly used successful worker combinations."""
        rows = self.db.query(
            "SELECT strategy_json, COUNT(*) AS uses FROM strategy_memory "
            "WHERE outcome='success' GROUP BY strategy_json ORDER BY uses DESC LIMIT ?",
            (limit,)
        )
        results = []
        for r in rows:
            try:
                s = json.loads(r["strategy_json"])
                results.append({"combination": s.get("worker_combination", []), "uses": r["uses"]})
            except Exception:
                pass
        return results


# ---------------------------------------------------------------------------
# Repair Memory
# ---------------------------------------------------------------------------

class RepairMemory:
    """Stores successful and failed repair actions for known error patterns."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(self, error_pattern: str, fix_action: str, success: bool) -> None:
        try:
            self.db.add_repair_memory(error_pattern, fix_action, success)
            log.info("RepairMemory: recorded fix for '%s'", error_pattern[:40])
        except Exception as exc:
            log.warning("RepairMemory: failed to record – %s", exc)

    def get_best_repair(self, error_pattern: str) -> Optional[str]:
        return self.db.get_best_repair(error_pattern)


# ---------------------------------------------------------------------------
# Project Memory
# ---------------------------------------------------------------------------

class ProjectMemory:
    """Stores generated projects, their templates, and complexity metrics."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(self, project_name: str, prompt: str, template_id: str, path: str, tags: List[str]) -> None:
        try:
            self.db.add_project_memory(project_name, prompt, template_id, path, tags)
            log.info("ProjectMemory: recorded project '%s'", project_name)
        except Exception as exc:
            log.warning("ProjectMemory: failed to record – %s", exc)

    def find_similar(self, prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.db.find_similar_projects(prompt, limit)


# ---------------------------------------------------------------------------
# JarvisMemory  (unified facade)
# ---------------------------------------------------------------------------

class JarvisMemory:
    """
    Unified memory facade. All four sub-systems accessible as attributes:
      memory.success   -> SuccessMemory
      memory.failure   -> FailureMemory
      memory.asset     -> AssetMemory
      memory.strategy  -> StrategyMemory

    Key retrieval methods:
      memory.find_similar_prompt(prompt)
      memory.get_best_strategy(prompt)
      memory.get_best_asset(category)
      memory.get_common_failures(prompt)
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self.success = SuccessMemory(db)
        self.prompt = self.success  # PromptMemory alias
        self.failure = FailureMemory(db)
        self.asset = AssetMemory(db)
        self.strategy = StrategyMemory(db)
        self.repair = RepairMemory(db)
        self.project = ProjectMemory(db)

    # ------------------------------------------------------------------
    # Primary retrieval APIs (used by Supervisor before planning)
    # ------------------------------------------------------------------

    def find_similar_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Returns the most similar prior successful execution record, or None.
        Includes: template_id, workers_used, assets_used, completion_time_secs,
        generated_files, reliability_score, similarity_score.
        """
        return self.success.find_similar(prompt)

    def get_best_strategy(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Returns the best known planning strategy for a similar prompt, or None.
        Includes: template_id, worker_combination, repair_strategy.
        """
        return self.strategy.get_best(prompt)

    def get_best_asset(self, category: str) -> Optional[str]:
        """
        Returns the asset_name with the highest success rate for a given role/category,
        or None if no data yet.
        """
        return self.asset.get_best_for_category(category)

    def get_common_failures(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Returns a list of known failure contexts for similar prompts.
        Each entry: {error, context: {worker, stage, fix_that_worked, retry_count}}.
        """
        return self.failure.get_common_failures(prompt)

    def get_best_repair(self, error_pattern: str) -> Optional[str]:
        """Returns the best fix_action for a given error pattern."""
        return self.repair.get_best_repair(error_pattern)

    def find_similar_projects(self, prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns previously generated projects that match the prompt."""
        return self.project.find_similar(prompt, limit)

    # ------------------------------------------------------------------
    # Write APIs (called by Supervisor / Pipeline after execution)
    # ------------------------------------------------------------------

    def record_success(
        self,
        job_id: str,
        prompt: str,
        template_id: str,
        workers_used: List[str],
        assets_used: List[str],
        completion_time_secs: float,
        generated_files: List[str],
        reliability_score: float = 1.0,
    ) -> None:
        """Record a successful execution. Also updates strategy memory."""
        self.success.record(
            job_id=job_id, prompt=prompt, template_id=template_id,
            workers_used=workers_used, assets_used=assets_used,
            completion_time_secs=completion_time_secs, generated_files=generated_files,
            reliability_score=reliability_score,
        )
        self.strategy.record(
            prompt=prompt, template_id=template_id,
            worker_combination=workers_used, outcome="success"
        )
        # Record each asset as a successful use
        for asset_name in assets_used:
            parts = asset_name.split(":")
            name = parts[0]
            source = parts[1] if len(parts) > 1 else "unknown"
            self.asset.record_usage(name, source, "general", success=True)

    def record_failure(
        self,
        prompt: str,
        worker: str,
        stage: str,
        error: str,
        stacktrace: str = "",
        fix_that_worked: str = "",
        retry_count: int = 0,
    ) -> None:
        """Record a failed execution stage."""
        self.failure.record(
            prompt=prompt, worker=worker, stage=stage, error=error,
            stacktrace=stacktrace, fix_that_worked=fix_that_worked, retry_count=retry_count
        )
        # Update strategy with the failure outcome so poor patterns are tracked
        self.strategy.record(
            prompt=prompt, template_id="unknown",
            worker_combination=[worker], repair_strategy=fix_that_worked,
            outcome="failure"
        )

    def record_asset_result(
        self,
        asset_name: str,
        asset_source: str,
        category: str,
        success: bool,
        import_issue: Optional[str] = None,
    ) -> None:
        """Record whether an asset was imported successfully."""
        self.asset.record_usage(asset_name, asset_source, category, success, import_issue)

    # ------------------------------------------------------------------
    # Backward-compat shims for existing SemanticMemory callers
    # ------------------------------------------------------------------

    def remember(self, job_id: str, prompt: str, template_id: str, outcome: str,
                 summary: Dict[str, Any]) -> None:
        """Legacy shim: wraps add_memory so existing Supervisor code still works."""
        try:
            self.db.add_memory(job_id, prompt, template_id, outcome, summary)
        except Exception as exc:
            log.warning("JarvisMemory.remember shim error: %s", exc)

    def recall(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.db.recall_memory(limit)

    def recall_similar(self, prompt: str) -> Optional[Dict[str, Any]]:
        return self.find_similar_prompt(prompt)

    # ------------------------------------------------------------------
    # Supervisor pre-planning context builder
    # ------------------------------------------------------------------

    def build_planning_context(self, prompt: str) -> Dict[str, Any]:
        """
        Called by Supervisor before dispatching a job.
        Returns a compact dict the planner can use to make smarter decisions:
          prior_success   – best similar prior success (or None)
          best_strategy   – best known strategy (or None)
          known_failures  – list of known failure patterns to avoid
          preferred_assets – dict of category -> best asset name
        """
        prior = self.find_similar_prompt(prompt)
        strategy = self.get_best_strategy(prompt)
        failures = self.get_common_failures(prompt)

        # Derive preferred assets from prior success asset list
        preferred: Dict[str, str] = {}
        if prior and prior.get("assets_used"):
            for asset_entry in prior["assets_used"]:
                parts = str(asset_entry).split(":")
                name = parts[0]
                cat = parts[2] if len(parts) > 2 else "general"
                preferred.setdefault(cat, name)

        ctx = {
            "prior_success": prior,
            "best_strategy": strategy,
            "known_failures": failures,
            "preferred_assets": preferred,
        }

        if prior:
            log.info(
                "Memory: found similar prior job (similarity=%.2f, template=%s)",
                prior.get("similarity_score", 0), prior.get("template_id")
            )
        else:
            log.info("Memory: no similar prior job found for prompt '%s...'", prompt[:40])

        return ctx
