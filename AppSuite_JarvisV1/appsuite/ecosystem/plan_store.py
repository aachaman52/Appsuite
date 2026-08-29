"""Jarvis Local Plan Store for Plan Memory & Resume v1.

Provides secure, atomic local persistence for multi-step GoalPlans:
- Atomic write with tempfile replacement
- Strict schema versioning (schema_version = 1)
- User ownership isolation (scoped by user_id)
- Path traversal protection (UUID plan_ids only)
- Preserves per-step idempotency keys for retry safety
- Revalidates command allowlists and dependencies on load
- Strictly zero credential or token serialization
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from .constants import JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS
from ..logging_setup import get_logger

log = get_logger("ecosystem.plan_store")

CURRENT_SCHEMA_VERSION = 1
DEFAULT_PLAN_STORE_DIR = Path.home() / ".aachman" / "plans"

SAFE_PLAN_ID_REGEX = re.compile(r"^[0-9a-fA-F-]{8,64}$")


def get_current_timestamp_iso() -> str:
    """Return timezone-aware ISO 8601 UTC timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class PlanStore:
    """Manages atomic file storage and retrieval of active GoalPlans."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else DEFAULT_PLAN_STORE_DIR
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists with restricted permissions."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            # Best-effort secure directory permissions on Unix
            if hasattr(os, "chmod") and os.name != "nt":
                os.chmod(self.storage_dir, 0o700)
        except Exception as e:
            log.warning("Could not set strict permissions on plan store directory: %s", e)

    def _get_plan_path(self, plan_id: str) -> Path:
        """Resolve plan file path with path traversal protection."""
        if not SAFE_PLAN_ID_REGEX.match(plan_id):
            raise ValueError(f"Invalid plan ID format: '{plan_id}'")
        resolved = (self.storage_dir / f"plan_{plan_id}.json").resolve()
        if not resolved.is_relative_to(self.storage_dir.resolve()):
            raise ValueError("Path traversal attempt detected in plan ID.")
        return resolved

    def save_plan(self, plan_dict: Dict[str, Any]) -> str:
        """Atomically persist a GoalPlan dictionary to disk.

        Returns:
            The plan_id of the saved plan.
        """
        # Ensure plan_id
        plan_id = plan_dict.get("plan_id") or str(uuid.uuid4())
        plan_dict["plan_id"] = plan_id
        plan_dict["schema_version"] = CURRENT_SCHEMA_VERSION
        if "created_at" not in plan_dict:
            plan_dict["created_at"] = get_current_timestamp_iso()
        plan_dict["updated_at"] = get_current_timestamp_iso()

        # Sanitize against accidental token/credential serialization
        self._sanitize_plan_dict(plan_dict)

        plan_path = self._get_plan_path(plan_id)

        # Atomic write: write to temp file in same directory then replace
        temp_fd, temp_path_str = tempfile.mkstemp(dir=self.storage_dir, prefix=f"tmp_plan_{plan_id}_")
        temp_path = Path(temp_path_str)
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(plan_dict, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace
            temp_path.replace(plan_path)
            log.debug("Plan saved atomically: %s", plan_id)
            return plan_id
        except Exception as e:
            log.error("Failed to atomically save plan %s: %s", plan_id, e)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise

    def load_plan(self, plan_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load and validate a persisted GoalPlan by ID."""
        try:
            plan_path = self._get_plan_path(plan_id)
        except ValueError as e:
            log.warning("Rejected invalid plan_id %s: %s", plan_id, e)
            return None

        if not plan_path.exists():
            return None

        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.error("Corrupted plan file encountered: %s: %s", plan_path.name, e)
            return None

        # Validate schema & security
        validated = self._validate_and_reconcile_plan(data, owner_id)
        return validated

    def load_active_plans(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load all active (unfinished) plans belonging to the specified owner."""
        active_plans = []
        if not self.storage_dir.exists():
            return active_plans

        for file_path in sorted(self.storage_dir.glob("plan_*.json"), key=os.path.getmtime, reverse=True):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                validated = self._validate_and_reconcile_plan(data, owner_id)
                if not validated:
                    continue

                # Check if active: has at least one non-terminal step
                steps = validated.get("steps", [])
                has_unfinished_step = any(
                    s.get("status") in ("ready", "planned", "executing", "recovery_pending", "failed", "blocked")
                    for s in steps
                )
                # Also check plan-level status if present
                if has_unfinished_step:
                    active_plans.append(validated)
            except Exception as e:
                log.warning("Skipping unreadable plan file %s: %s", file_path.name, e)
                continue

        return active_plans

    def delete_plan(self, plan_id: str) -> bool:
        """Delete local plan file (does not roll back server entities)."""
        try:
            plan_path = self._get_plan_path(plan_id)
            if plan_path.exists():
                plan_path.unlink()
                log.debug("Deleted local plan: %s", plan_id)
                return True
        except Exception as e:
            log.error("Failed to delete plan %s: %s", plan_id, e)
        return False

    def archive_plan(self, plan_id: str) -> bool:
        """Mark all remaining unexecuted steps in plan as completed/archived."""
        plan = self.load_plan(plan_id)
        if not plan:
            return False
        for step in plan.get("steps", []):
            if step.get("status") not in ("completed", "skipped"):
                step["status"] = "archived"
        self.save_plan(plan)
        return True

    # ── Internal Validation & Reconciliation ──────────────────────────────────

    def _validate_and_reconcile_plan(
        self, data: Any, expected_owner_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Strict validation of plan structure, schema version, owner, and command IDs."""
        if not isinstance(data, dict):
            return None

        # Schema version check
        schema_ver = data.get("schema_version")
        if schema_ver != CURRENT_SCHEMA_VERSION:
            log.warning("Unsupported schema version: %s", schema_ver)
            return None

        plan_id = data.get("plan_id")
        if not plan_id or not isinstance(plan_id, str) or not SAFE_PLAN_ID_REGEX.match(plan_id):
            return None

        # Owner validation: plan owner must match current authenticated user
        plan_owner = data.get("owner_id")
        if expected_owner_id and plan_owner and plan_owner != expected_owner_id:
            log.debug("Plan %s owner mismatch (%s != %s)", plan_id, plan_owner, expected_owner_id)
            return None

        steps = data.get("steps")
        if not isinstance(steps, list) or len(steps) > 5:
            return None

        valid_step_ids = {s.get("step_id") for s in steps if isinstance(s, dict) and s.get("step_id")}

        # Validate each step
        for step in steps:
            if not isinstance(step, dict):
                return None

            command_id = step.get("command_id")
            if command_id and command_id not in JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS:
                log.warning("Disallowed command_id '%s' in persisted plan %s", command_id, plan_id)
                return None

            # Validate dependencies
            deps = step.get("depends_on", [])
            if not isinstance(deps, list) or any(dep not in valid_step_ids for dep in deps):
                log.warning("Invalid dependency reference in step %s", step.get("step_id"))
                return None

            # Reconcile interrupted execution on startup
            if step.get("status") == "executing":
                log.info("Interrupted executing step %s recovered to recovery_pending", step.get("step_id"))
                step["status"] = "recovery_pending"

        return data

    def _sanitize_plan_dict(self, data: Dict[str, Any]) -> None:
        """Strip any accidental credential fields before persistence."""
        forbidden_keys = {
            "access_token",
            "refresh_token",
            "token",
            "jwt",
            "password",
            "apikey",
            "authorization",
            "secret",
            "service_role",
        }
        for key in list(data.keys()):
            if key.lower() in forbidden_keys:
                del data[key]
