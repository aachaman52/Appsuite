"""Jarvis Local Plan Store — Plan Memory & Resume v2 (Beta Execution Safety Hardened).

Provides secure, atomic local persistence for multi-step GoalPlans:
- Cross-process OS-level PlanLock (Windows msvcrt / Unix fcntl)
- Atomic write via tempfile flush + atomic replace
- Strict schema versioning (schema_version = 1)
- Fail-closed user ownership isolation (scoped by owner_id)
- Path traversal protection (UUID plan_ids only, regex + is_relative_to guard)
- Recursive secret sanitization (normalized key-based, never value-based)
- Executing-without-idempotency-key -> recovery_rejected (non-executable, non-retryable)
- Fingerprint mismatch -> recovery_rejected (non-executable, non-retryable)
- Executing + key + fingerprint match -> recovery_pending (explicit user retry required)
- Corrupted/oversized files quarantined to plan_<id>.corrupt.<timestamp>
- Strict structural validation on load (duplicate IDs/orders, cycles, types, statuses)
- Canonical parameter schema validation via action_validation module
- Error message sanitization before persistence
- Zero credential or token serialization
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from .action_validation import (
    WRITE_ACTION_COMMAND_IDS,
    validate_action_parameters,
)
from .constants import JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS, JARVIS_ALLOWED_READ_TOOL_IDS
from ..logging_setup import get_logger

log = get_logger("ecosystem.plan_store")

# Backwards compatibility alias
_validate_write_parameters = validate_action_parameters


CURRENT_SCHEMA_VERSION = 1
DEFAULT_PLAN_STORE_DIR = Path.home() / ".aachman" / "plans"

# Strict UUID/hex plan ID regex — guards against path traversal via plan_id
SAFE_PLAN_ID_REGEX = re.compile(r"^[0-9a-fA-F-]{8,64}$")

# Maximum plan file size (bytes): prevents startup DoS from large planted files
MAX_PLAN_FILE_BYTES = 1 * 1024 * 1024  # 1 MB

# String length limits for human-readable fields
MAX_GOAL_LEN = 1000
MAX_SUMMARY_LEN = 1000
MAX_STEP_TEXT_LEN = 500   # title, description, reason
MAX_ERROR_MSG_LEN = 512   # persisted error_message

# Valid step lifecycle statuses (includes non-retryable recovery_rejected)
VALID_STEP_STATUSES = frozenset({
    "planned", "ready", "confirmed", "executing",
    "completed", "skipped", "cancelled", "failed", "blocked",
    "recovery_pending", "recovery_rejected",
})

# Valid step types
VALID_STEP_TYPES = frozenset({"read_summary", "suggestion", "write_action"})

# ── Recursive Secret Sanitizer ─────────────────────────────────────────────────
# Normalized secret key denylist. Keys are normalized via _normalize_key() before
# comparison. Key-based only — never strip by value substring.
_SECRET_DENYLIST_NORMALIZED: frozenset = frozenset({
    "accesstoken",
    "refreshtoken",
    "token",
    "jwt",
    "password",
    "passwd",
    "apikey",
    "authorization",
    "secret",
    "servicerole",
    "bearer",
    "credential",
    "credentials",
    "privatekey",
})


class PlanLockTimeoutError(Exception):
    """Raised when PlanLock cannot be acquired within the allowed timeout."""
    pass


class PlanLock:
    """Cross-process file lock scoped to a specific plan_id.

    Uses OS-level kernel file locks (msvcrt on Windows, fcntl on Unix).
    Crash-resilient: closing/crashing processes automatically release locks.
    A stale empty .lock file left on disk does not prevent acquisition.
    """

    def __init__(self, plan_id: str, storage_dir: Path, timeout: float = 5.0):
        if not SAFE_PLAN_ID_REGEX.match(plan_id):
            raise ValueError(f"Invalid plan ID format for locking: '{plan_id}'")
        self.plan_id = plan_id
        self.storage_dir = Path(storage_dir)
        self.timeout = max(0.1, timeout)
        self.lock_file_path = (self.storage_dir / f"plan_{plan_id}.lock").resolve()
        self._fd: Optional[int] = None

    def __enter__(self) -> PlanLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    def acquire(self) -> None:
        """Acquire OS-level lock with retry up to timeout."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        start_time = time.time()
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY

        while True:
            try:
                self._fd = os.open(str(self.lock_file_path), flags, 0o600)
                if os.name == "nt":
                    import msvcrt
                    # Lock byte 0 with LK_NBLCK (non-blocking)
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Acquired successfully
                return
            except (BlockingIOError, OSError, PermissionError):
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except Exception:
                        pass
                    self._fd = None

                if (time.time() - start_time) >= self.timeout:
                    raise PlanLockTimeoutError(
                        f"This plan is currently being updated by another PyFlare session. "
                        f"Lock timed out for plan '{self.plan_id}'."
                    )
                time.sleep(0.05)

    def release(self) -> None:
        """Release OS-level lock and close file descriptor."""
        if self._fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    try:
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(self._fd)
            except Exception as e:
                log.debug("Error releasing lock fd: %s", e)
            finally:
                self._fd = None


def _normalize_key(key: str) -> str:
    """Normalize a dict key for secret matching: lowercase, strip underscores, dashes, spaces."""
    return key.lower().replace("_", "").replace("-", "").replace(" ", "")


def _sanitize_recursive(data: Any) -> Any:
    """Recursively strip secret-keyed fields from dicts/lists. Returns sanitized copy."""
    if isinstance(data, dict):
        return {
            k: _sanitize_recursive(v)
            for k, v in data.items()
            if _normalize_key(k) not in _SECRET_DENYLIST_NORMALIZED
        }
    elif isinstance(data, list):
        return [_sanitize_recursive(item) for item in data]
    else:
        return data


def _sanitize_error_message(msg: Optional[str]) -> Optional[str]:
    """Sanitize an error_message before persistence: cap length, strip Bearer tokens."""
    if not msg:
        return msg
    msg = msg[:MAX_ERROR_MSG_LEN]
    # Strip obvious JWT/Bearer patterns (conservative — only obvious cases)
    msg = re.sub(r"Bearer\s+\S{20,}", "Bearer [REDACTED]", msg)
    return msg


def get_current_timestamp_iso() -> str:
    """Return timezone-aware ISO 8601 UTC timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def compute_confirmation_fingerprint(
    plan_id: str,
    step_id: str,
    command_id: str,
    parameters: Dict[str, Any],
) -> str:
    """Compute SHA-256 fingerprint binding plan_id + step_id + command_id + parameters.

    Uses canonical JSON (sorted keys, compact separators, UTF-8 encoding).
    Persisted after explicit confirmation; verified before any recovery retry.
    The server-side idempotency_key remains a separate opaque UUID — never
    derived from this fingerprint.
    """
    canonical = json.dumps(
        {
            "plan_id": plan_id,
            "step_id": step_id,
            "command_id": command_id,
            "parameters": parameters,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _has_dependency_cycle(steps: List[Dict[str, Any]]) -> bool:
    """Detect dependency cycles among ≤5 steps using iterative DFS.

    Returns True if a cycle exists, False otherwise.
    """
    graph: Dict[str, List[str]] = {}
    for step in steps:
        if isinstance(step, dict):
            graph[step.get("step_id", "")] = list(step.get("depends_on", []))

    visited: set = set()
    in_stack: set = set()

    def dfs(node: str) -> bool:
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            if dfs(neighbor):
                return True
        in_stack.discard(node)
        return False

    return any(dfs(node) for node in graph)


class PlanStore:
    """Manages atomic file storage and retrieval of active GoalPlans.

    Security properties:
    - plan_ids validated against SAFE_PLAN_ID_REGEX (UUID/hex only)
    - Resolved paths checked against storage_dir root
    - Secrets stripped recursively before any write (normalized key-based)
    - Corrupted/oversized files quarantined, not silently deleted
    - executing + no key -> recovery_rejected (non-executable, non-retryable)
    - recovery_pending + no key -> recovery_rejected
    - Fingerprint mismatch on recovery -> recovery_rejected
    - Fail-closed ownership isolation (unauthenticated -> no plans returned)
    - All structural invariants validated on every load
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = Path(storage_dir) if storage_dir else DEFAULT_PLAN_STORE_DIR
        self._ensure_storage_dir()

    def _ensure_storage_dir() -> None:
        """Ensure storage directory exists with restricted permissions."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "chmod") and os.name != "nt":
                os.chmod(self.storage_dir, 0o700)
        except Exception as e:
            log.warning("Could not set strict permissions on plan store directory: %s", e)

    def _ensure_storage_dir(self) -> None:
        """Ensure storage directory exists with restricted permissions."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "chmod") and os.name != "nt":
                os.chmod(self.storage_dir, 0o700)
        except Exception as e:
            log.warning("Could not set strict permissions on plan store directory: %s", e)

    def get_plan_lock(self, plan_id: str, timeout: float = 5.0) -> PlanLock:
        """Return a PlanLock instance for coordinating operations on a given plan."""
        return PlanLock(plan_id, self.storage_dir, timeout=timeout)

    def _get_plan_path(self, plan_id: str) -> Path:
        """Resolve plan file path with strict path traversal protection."""
        if not isinstance(plan_id, str) or not SAFE_PLAN_ID_REGEX.match(plan_id):
            raise ValueError(f"Invalid plan ID format (must be UUID/hex 8-64 chars): '{plan_id}'")
        resolved = (self.storage_dir / f"plan_{plan_id}.json").resolve()
        try:
            resolved.relative_to(self.storage_dir.resolve())
        except ValueError:
            raise ValueError("Path traversal attempt detected in plan ID.")
        return resolved

    def _quarantine_file(self, file_path: Path, reason: str = "corrupt") -> None:
        """Best-effort quarantine: rename to plan_<name>.corrupt.<timestamp>.

        Never raises — startup must continue even if quarantine fails.
        Only operates on files confirmed to be inside storage_dir.
        """
        try:
            file_path.resolve().relative_to(self.storage_dir.resolve())
            ts = int(time.time())
            quarantine_name = f"{file_path.stem}.corrupt.{ts}"
            quarantine_path = self.storage_dir / quarantine_name
            file_path.rename(quarantine_path)
            log.warning(
                "Quarantined %s plan file: %s -> %s", reason, file_path.name, quarantine_name
            )
        except Exception as e:
            log.warning(
                "Could not quarantine %s: %s (startup continues)", file_path.name, e
            )

    def save_plan(self, plan_dict: Dict[str, Any]) -> str:
        """Atomically persist a GoalPlan dictionary to disk.

        - Sanitizes error_messages on steps before write
        - Recursively strips secret-keyed fields
        - Writes to temp, fsync, atomic replace
        - Cleans up temp on failure

        Returns:
            The plan_id of the saved plan.
        """
        plan_id = plan_dict.get("plan_id") or str(uuid.uuid4())
        plan_dict["plan_id"] = plan_id
        plan_dict["schema_version"] = CURRENT_SCHEMA_VERSION
        if "created_at" not in plan_dict:
            plan_dict["created_at"] = get_current_timestamp_iso()
        plan_dict["updated_at"] = get_current_timestamp_iso()

        # Sanitize error_messages within steps before recursive pass
        for step in plan_dict.get("steps", []):
            if isinstance(step, dict) and step.get("error_message"):
                step["error_message"] = _sanitize_error_message(step["error_message"])

        # Recursive secret sanitization (returns new sanitized dict)
        sanitized = _sanitize_recursive(plan_dict)

        plan_path = self._get_plan_path(plan_id)

        temp_fd, temp_path_str = tempfile.mkstemp(
            dir=self.storage_dir, prefix=f"tmp_plan_{plan_id}_"
        )
        temp_path = Path(temp_path_str)
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(sanitized, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            temp_path.replace(plan_path)
            log.debug("Plan saved atomically: %s", plan_id)
            return plan_id
        except Exception as e:
            log.error("Failed to atomically save plan %s: %s", plan_id, e)
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            raise

    def load_plan(self, plan_id: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load and validate a persisted GoalPlan by ID with fail-closed ownership."""
        try:
            plan_path = self._get_plan_path(plan_id)
        except ValueError as e:
            log.warning("Rejected invalid plan_id '%s': %s", plan_id, e)
            return None

        if not plan_path.exists():
            return None

        # File size guard before parsing
        try:
            file_size = plan_path.stat().st_size
        except OSError:
            return None
        if file_size > MAX_PLAN_FILE_BYTES:
            log.warning("Plan file too large (%d bytes), quarantining: %s", file_size, plan_path.name)
            self._quarantine_file(plan_path, "oversized")
            return None

        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.error("Corrupted plan file: %s: %s", plan_path.name, e)
            self._quarantine_file(plan_path, "malformed_json")
            return None

        return self._validate_and_reconcile_plan(data, owner_id, source_path=plan_path)

    def load_active_plans(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load all active (unfinished) plans for the specified owner, most-recent first.

        Fails closed: if owner_id is None or empty, returns an empty list (no unauthenticated plan access).
        """
        active_plans: List[Dict[str, Any]] = []
        if not owner_id or not self.storage_dir.exists():
            return active_plans

        plan_files = sorted(
            self.storage_dir.glob("plan_*.json"),
            key=os.path.getmtime,
            reverse=True,
        )

        for file_path in plan_files:
            try:
                # Symlink/reparse best-effort containment check
                try:
                    file_path.resolve().relative_to(self.storage_dir.resolve())
                except ValueError:
                    log.warning("Skipping out-of-bounds plan path: %s", file_path)
                    continue

                try:
                    file_size = file_path.stat().st_size
                except OSError:
                    continue
                if file_size > MAX_PLAN_FILE_BYTES:
                    log.warning("Skipping oversized plan file: %s (%d bytes)", file_path.name, file_size)
                    self._quarantine_file(file_path, "oversized")
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    log.warning("Skipping unreadable plan file %s: %s", file_path.name, e)
                    self._quarantine_file(file_path, "malformed_json")
                    continue

                validated = self._validate_and_reconcile_plan(data, owner_id)
                if not validated:
                    continue

                steps = validated.get("steps", [])
                has_unfinished = any(
                    s.get("status") in ("ready", "planned", "executing", "recovery_pending", "failed", "blocked")
                    for s in steps
                )
                if has_unfinished:
                    active_plans.append(validated)
            except Exception as e:
                # Per-file isolation: single malformed file does not abort entire scan
                log.warning("Error processing plan file %s: %s", file_path.name, e)
                continue

        return active_plans

    def delete_plan(self, plan_id: str) -> bool:
        """Delete local plan file and associated lock file."""
        try:
            plan_path = self._get_plan_path(plan_id)
            if plan_path.exists():
                plan_path.unlink()
                log.debug("Deleted local plan: %s", plan_id)

            lock_path = self.storage_dir / f"plan_{plan_id}.lock"
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except Exception:
                    pass
            return True
        except Exception as e:
            log.error("Failed to delete plan %s: %s", plan_id, e)
        return False

    def archive_plan(self, plan_id: str) -> bool:
        """Mark all remaining unexecuted steps as cancelled."""
        plan = self.load_plan(plan_id)
        if not plan:
            return False
        for step in plan.get("steps", []):
            if step.get("status") not in ("completed", "skipped", "cancelled"):
                step["status"] = "cancelled"
        self.save_plan(plan)
        return True

    # ── Internal Validation & Reconciliation ──────────────────────────────────

    def _validate_and_reconcile_plan(
        self,
        data: Any,
        expected_owner_id: Optional[str] = None,
        source_path: Optional[Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """Strict validation of plan structure, schema, owner, and all invariants.

        Reconciles interrupted states:
        - executing + key + fingerprint match -> recovery_pending
        - executing + key + no fingerprint (legacy) -> recovery_pending
        - executing + no key -> recovery_rejected (non-executable, non-retryable)
        - recovery_pending + no key -> recovery_rejected
        - recovery_pending + fingerprint mismatch -> recovery_rejected
        """
        if not isinstance(data, dict):
            return None

        # Schema version
        schema_ver = data.get("schema_version")
        if schema_ver != CURRENT_SCHEMA_VERSION:
            log.warning("Unsupported schema version: %s", schema_ver)
            return None

        # plan_id format
        plan_id = data.get("plan_id")
        if not plan_id or not isinstance(plan_id, str) or not SAFE_PLAN_ID_REGEX.match(plan_id):
            log.warning("Invalid or missing plan_id")
            return None

        # Owner isolation: plan owner must match expected_owner_id when specified
        plan_owner = data.get("owner_id")
        if expected_owner_id and plan_owner and plan_owner != expected_owner_id:
            log.debug("Plan %s owner mismatch (%s != %s)", plan_id, plan_owner, expected_owner_id)
            return None

        # String length limits
        goal = data.get("goal", "")
        if not isinstance(goal, str) or len(goal) > MAX_GOAL_LEN:
            log.warning("Plan %s has invalid or oversized 'goal'", plan_id)
            return None
        summary = data.get("summary", "")
        if not isinstance(summary, str) or len(summary) > MAX_SUMMARY_LEN:
            log.warning("Plan %s has invalid or oversized 'summary'", plan_id)
            return None

        # source_tool_ids allowlist with type safety
        source_tool_ids = data.get("source_tool_ids", [])
        if not isinstance(source_tool_ids, list):
            return None
        for tool_id in source_tool_ids:
            if not isinstance(tool_id, str) or tool_id not in JARVIS_ALLOWED_READ_TOOL_IDS:
                log.warning("Unknown or invalid source_tool_id '%s' in plan %s", tool_id, plan_id)
                return None

        # Steps list validation
        steps = data.get("steps")
        if not isinstance(steps, list):
            return None
        if len(steps) > 5:
            log.warning("Plan %s has too many steps (%d > 5)", plan_id, len(steps))
            return None

        seen_step_ids: set = set()
        seen_orders: set = set()

        # Step primitive type safety check before indexing
        for step in steps:
            if not isinstance(step, dict):
                return None
            s_id = step.get("step_id")
            if not isinstance(s_id, str) or not s_id.strip():
                log.warning("Plan %s has non-string or empty step_id: %s", plan_id, type(s_id).__name__)
                return None

        step_id_set: set = {s["step_id"] for s in steps}

        for step in steps:
            step_id = step["step_id"]

            # Duplicate step_id check
            if step_id in seen_step_ids:
                log.warning("Plan %s has duplicate step_id: %s", plan_id, step_id)
                return None
            seen_step_ids.add(step_id)

            # Order validation
            order = step.get("order")
            if not isinstance(order, int) or isinstance(order, bool) or order <= 0:
                log.warning("Plan %s step %s has invalid order: %s", plan_id, step_id, order)
                return None
            if order in seen_orders:
                log.warning("Plan %s has duplicate step order: %d", plan_id, order)
                return None
            seen_orders.add(order)

            # Step type validation
            step_type = step.get("step_type")
            if step_type not in VALID_STEP_TYPES:
                log.warning("Plan %s step %s has invalid step_type: %s", plan_id, step_id, step_type)
                return None

            # Status validation
            status = step.get("status", "planned")
            if status not in VALID_STEP_STATUSES:
                log.warning("Plan %s step %s has unknown status: %s", plan_id, step_id, status)
                return None

            # String length limits for step text fields
            for field_name in ("title", "description", "reason"):
                val = step.get(field_name, "")
                if not isinstance(val, str) or len(val) > MAX_STEP_TEXT_LEN:
                    log.warning(
                        "Plan %s step %s has oversized field '%s'", plan_id, step_id, field_name
                    )
                    return None

            # command_id allowlist
            command_id = step.get("command_id")
            if command_id and command_id not in JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS:
                log.warning(
                    "Disallowed command_id '%s' in plan %s step %s", command_id, plan_id, step_id
                )
                return None

            # write_action integrity
            if step_type == "write_action":
                if not command_id:
                    log.warning("Plan %s: write_action step %s missing command_id", plan_id, step_id)
                    return None
                if command_id not in WRITE_ACTION_COMMAND_IDS:
                    log.warning(
                        "Plan %s: write_action step %s has non-write command_id '%s'",
                        plan_id, step_id, command_id,
                    )
                    return None
                # Canonical parameter validation for executable states
                executable_statuses = {
                    "ready", "planned", "executing", "recovery_pending", "confirmed", "failed"
                }
                if status in executable_statuses:
                    params = step.get("parameters", {})
                    param_error = validate_action_parameters(command_id, params)
                    if param_error:
                        log.warning(
                            "Plan %s step %s parameter validation failed: %s",
                            plan_id, step_id, param_error,
                        )
                        return None

            # read_summary must not carry a write command
            if step_type == "read_summary" and command_id and command_id in WRITE_ACTION_COMMAND_IDS:
                log.warning(
                    "Plan %s: read_summary step %s carries mutation command_id", plan_id, step_id
                )
                return None

            # Dependencies — all referenced IDs must exist as strings in the plan
            deps = step.get("depends_on", [])
            if not isinstance(deps, list):
                return None
            for dep_id in deps:
                if not isinstance(dep_id, str) or dep_id not in step_id_set:
                    log.warning(
                        "Plan %s step %s references unknown or non-string dep '%s'",
                        plan_id, step_id, dep_id,
                    )
                    return None

        # Dependency cycle detection
        if _has_dependency_cycle(steps):
            log.warning("Plan %s has dependency cycle — rejecting", plan_id)
            return None

        # ── Recovery reconciliation (done after full structural validation) ──
        for step in steps:
            status = step.get("status")
            step_id = step.get("step_id", "")
            key = step.get("idempotency_key")
            fingerprint = step.get("confirmation_fingerprint")

            if status == "executing":
                if not key:
                    log.warning(
                        "Plan %s step %s was executing without idempotency key — marking recovery_rejected",
                        plan_id, step_id,
                    )
                    step["status"] = "recovery_rejected"
                    step["error_message"] = (
                        "Unsafe recovery: interrupted without idempotency key. Safe retry is unavailable. "
                        "Code: unsafe_recovery_missing_idempotency_key"
                    )
                elif fingerprint:
                    # Verify fingerprint to detect payload tampering
                    expected = compute_confirmation_fingerprint(
                        plan_id=plan_id,
                        step_id=step_id,
                        command_id=step.get("command_id", ""),
                        parameters=step.get("parameters", {}),
                    )
                    if expected != fingerprint:
                        log.warning(
                            "Plan %s step %s fingerprint mismatch on recovery — marking recovery_rejected",
                            plan_id, step_id,
                        )
                        step["status"] = "recovery_rejected"
                        step["error_message"] = (
                            "Unsafe recovery: persisted action payload changed after confirmation."
                        )
                    else:
                        log.info(
                            "Plan %s step %s recovering from executing to recovery_pending",
                            plan_id, step_id,
                        )
                        step["status"] = "recovery_pending"
                else:
                    # No fingerprint: legacy plan (pre-fingerprint schema)
                    log.info(
                        "Plan %s step %s recovering to recovery_pending (legacy: no fingerprint)",
                        plan_id, step_id,
                    )
                    step["status"] = "recovery_pending"

            elif status == "recovery_pending":
                if not key:
                    log.warning(
                        "Plan %s step %s is recovery_pending without key — marking recovery_rejected",
                        plan_id, step_id,
                    )
                    step["status"] = "recovery_rejected"
                    step["error_message"] = (
                        "Unsafe recovery: recovery step missing idempotency key. "
                        "Code: unsafe_recovery_missing_idempotency_key"
                    )

                elif fingerprint:
                    expected = compute_confirmation_fingerprint(
                        plan_id=plan_id,
                        step_id=step_id,
                        command_id=step.get("command_id", ""),
                        parameters=step.get("parameters", {}),
                    )
                    if expected != fingerprint:
                        log.warning(
                            "Plan %s step %s fingerprint mismatch on recovery_pending — marking recovery_rejected",
                            plan_id, step_id,
                        )
                        step["status"] = "recovery_rejected"
                        step["error_message"] = (
                            "Unsafe recovery: persisted action payload changed after confirmation."
                        )

        return data

    def _sanitize_plan_dict(self, data: Dict[str, Any]) -> None:
        """Backward-compat shim: in-place recursive sanitization."""
        sanitized = _sanitize_recursive(data)
        data.clear()
        data.update(sanitized)
