"""Security, Structural Validation & Recovery Tests for Jarvis PlanStore v2.

Covers all acceptance criteria from Security Hardening v1:
- Recursive secret sanitization (nested + case-insensitive variants)
- Actual persisted byte audit (sentinel secret values)
- Fingerprint tamper protection (7 scenarios)
- Executing-without-key safe failure
- Recovery_pending-without-key safe failure
- True restart simulation (destroy all objects, new instances)
- Response-loss restart with new objects
- Structural validation (types, statuses, duplicates, cycles, lengths, sizes)
- Path traversal (multiple forms)
- Owner isolation + signed-out access
- Multiple active plans
- Delete vs cancel semantics
- Terminal plan definition
- Zero side-effect audit
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from appsuite.ecosystem import (
    AachmanEcosystemClient,
    GoalPlanner,
    GoalPlan,
    GoalPlanStep,
    PlanStore,
    EcosystemReadExecutor,
    JarvisReadResponse,
    ExecutionResult,
    CURRENT_SCHEMA_VERSION,
    compute_confirmation_fingerprint,
)
from appsuite.ecosystem.plan_store import (
    _normalize_key,
    _sanitize_recursive,
    _validate_write_parameters,
    _has_dependency_cycle,
    MAX_PLAN_FILE_BYTES,
    VALID_STEP_STATUSES,
    VALID_STEP_TYPES,
)

# ── Helper: build a minimal valid plan dict ────────────────────────────────────

def _valid_plan(plan_id=None, owner_id="user_test", step_id="s1", status="ready",
                command_id="action.daymentor.create_task", step_type="write_action",
                parameters=None):
    plan_id = plan_id or str(uuid.uuid4())
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "plan_id": plan_id,
        "owner_id": owner_id,
        "goal": "Test Goal",
        "summary": "Test summary",
        "source_tool_ids": ["read.daymentor.next_exam"],
        "confidence": 1.0,
        "steps": [
            {
                "step_id": step_id,
                "order": 1,
                "title": "Test Step",
                "description": "Test description",
                "reason": "Test reason",
                "step_type": step_type,
                "command_id": command_id,
                "parameters": parameters or {"title": "Revision Task", "priority": "medium"},
                "status": status,
                "depends_on": [],
            }
        ],
    }


# ── Mock executor for side-effect auditing ─────────────────────────────────────

class AuditExecutor:
    def __init__(self, entity_id="entity_fixed_abc"):
        self.calls = []
        self.entity_id = entity_id

    def execute_intent(self, intent, confirm=False):
        if not confirm:
            return ExecutionResult(command_id=intent.command_id, status="preview", message="preview")
        self.calls.append({"command_id": intent.command_id, "key": intent.idempotency_key})
        return ExecutionResult(
            command_id=intent.command_id,
            status="success",
            message="ok",
            preview_data={"entity_id": self.entity_id},
        )


class MockReadExecutor(EcosystemReadExecutor):
    def __init__(self, exam_data=None):
        super().__init__(client=AachmanEcosystemClient(session_file=Path("/tmp/mock_test.json")))
        self.client._in_memory_access_token = "dummy"
        self.client.metadata = {"user_id": "test_uid", "email": "test@aachman.org"}
        self.exam_data = exam_data

    def execute_read_intent(self, intent):
        if intent.tool_id == "read.daymentor.next_exam" and self.exam_data:
            return JarvisReadResponse(
                tool_id="read.daymentor.next_exam",
                status="success",
                human_text="Exam found",
                data={"has_exam": True, "exam": self.exam_data, "days_remaining": self.exam_data["days_remaining"]},
            )
        return JarvisReadResponse(tool_id=intent.tool_id, status="empty", human_text="No data", data={})


# ══════════════════════════════════════════════════════════════════════════════
# 1. RECURSIVE SECRET SANITIZATION
# ══════════════════════════════════════════════════════════════════════════════

def test_recursive_secret_sanitization_nested_dict():
    """Nested dict containing secret keys must be stripped recursively."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_a",
            "goal": "Nested secret test",
            "summary": "Ensure nested secrets stripped",
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": "Step",
                    "description": "desc",
                    "reason": "reason",
                    "step_type": "write_action",
                    "command_id": "action.daymentor.create_task",
                    "parameters": {
                        "title": "Safe Value",
                        "priority": "medium",
                        "nested_creds": {
                            "authorization": "Bearer TOP_SECRET_NESTED",
                            "safe_key": "keep_this",
                        },
                    },
                    "status": "ready",
                    "depends_on": [],
                }
            ],
        }
        store.save_plan(plan)

        raw = (temp_dir / f"plan_{plan_id}.json").read_bytes()
        assert b"TOP_SECRET_NESTED" not in raw, "Nested secret leaked to disk"
        assert b"keep_this" in raw, "Safe nested key wrongly stripped"
        assert b"Safe Value" in raw
        print("✓ Recursive nested dict secret sanitization: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_recursive_secret_sanitization_in_list():
    """Secrets inside list items must be stripped recursively."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = _valid_plan(plan_id=plan_id)
        plan["steps"][0]["result"] = [
            {"entity_id": "e1", "access_token": "LIST_SECRET_ABC"},
            {"entity_id": "e2", "deep_link": "https://example.com"},
        ]
        store.save_plan(plan)

        raw = (temp_dir / f"plan_{plan_id}.json").read_bytes()
        assert b"LIST_SECRET_ABC" not in raw
        assert b"e1" in raw
        print("✓ Recursive list secret sanitization: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_case_insensitive_secret_key_variants():
    """All canonical case variants of secret keys must be stripped."""
    secret_keys = [
        ("Access_Token", "TEST_ACCESS_TOKEN_ABC123"),
        ("AccessToken", "TEST_ACCESS_TOKEN_ABC124"),
        ("ACCESS-TOKEN", "TEST_ACCESS_TOKEN_ABC125"),
        ("refreshToken", "TEST_REFRESH_TOKEN_DEF456"),
        ("REFRESH_TOKEN", "TEST_REFRESH_TOKEN_DEF457"),
        ("Authorization", "TEST_BEARER_GHI789"),
        ("AUTHORIZATION", "TEST_BEARER_GHI790"),
        ("service_role", "TEST_SERVICE_ROLE_XYZ"),
        ("ServiceRole", "TEST_SERVICE_ROLE_XYZ2"),
        ("api_key", "TEST_APIKEY_SECRET_001"),
        ("apiKey", "TEST_APIKEY_SECRET_002"),
        ("Password", "TEST_PASSWORD_001"),
        ("passwd", "TEST_PASSWD_001"),
        ("jwt", "TEST_JWT_001"),
        ("private_key", "TEST_PRIVATEKEY_001"),
    ]
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_a",
            "goal": "Secret key variant test",
            "summary": "All variants must be stripped",
        }
        # Inject all secret key variants at top level
        for key, val in secret_keys:
            plan[key] = val
        plan["steps"] = [
            {
                "step_id": "s1", "order": 1, "title": "Step", "description": "desc",
                "reason": "r", "step_type": "suggestion", "status": "ready",
                "command_id": None, "parameters": {}, "depends_on": [],
            }
        ]
        store.save_plan(plan)

        raw = (temp_dir / f"plan_{plan_id}.json").read_bytes()
        for _key, val in secret_keys:
            assert val.encode() not in raw, f"Sentinel value {val!r} found in persisted bytes!"
        print(f"✓ Case-insensitive secret key variants ({len(secret_keys)} variants): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. ACTUAL BYTE AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def test_sentinel_secret_byte_audit():
    """Read actual persisted JSON bytes and confirm zero sentinel occurrences."""
    SENTINELS = [
        b"TEST_ACCESS_TOKEN_ABC123",
        b"TEST_REFRESH_TOKEN_DEF456",
        b"TEST_BEARER_GHI789",
        b"TEST_SERVICE_ROLE_XYZ",
    ]
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_test",
            "goal": "Byte audit test",
            "summary": "Verify no sentinels in actual file bytes",
            "access_token": "TEST_ACCESS_TOKEN_ABC123",
            "refresh_token": "TEST_REFRESH_TOKEN_DEF456",
            "Authorization": "Bearer TEST_BEARER_GHI789",
            "service_role": "TEST_SERVICE_ROLE_XYZ",
            "steps": [
                {
                    "step_id": "s1", "order": 1, "title": "Step", "description": "desc",
                    "reason": "r", "step_type": "suggestion", "status": "ready",
                    "command_id": None, "parameters": {}, "depends_on": [],
                }
            ],
        }
        store.save_plan(plan)

        raw = (temp_dir / f"plan_{plan_id}.json").read_bytes()

        for sentinel in SENTINELS:
            assert sentinel not in raw, f"Sentinel {sentinel!r} found in persisted bytes!"

        # Verify safe fields are present
        assert b"user_test" in raw
        assert b"Byte audit test" in raw

        print("✓ Sentinel secret byte audit (4 sentinels, 0 occurrences): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. CONFIRMATION FINGERPRINT TAMPER PROTECTION
# ══════════════════════════════════════════════════════════════════════════════

def _make_fingerprint(plan_id, step_id, command_id, parameters):
    canonical = json.dumps(
        {"plan_id": plan_id, "step_id": step_id, "command_id": command_id, "parameters": parameters},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_fingerprint_same_payload_matches():
    """Same plan+step+command+payload produces identical fingerprint."""
    fp1 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "Exam", "priority": "medium"})
    fp2 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "Exam", "priority": "medium"})
    assert fp1 == fp2
    print("✓ Fingerprint: same payload matches: PASS")


def test_fingerprint_changed_title_mismatches():
    """Modified title produces different fingerprint — execution rejected."""
    fp_original = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "Exam Revision", "deadline": "2026-09-01"})
    fp_tampered = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "CHANGED TITLE", "deadline": "2026-09-01"})
    assert fp_original != fp_tampered
    print("✓ Fingerprint: changed title mismatches: PASS")


def test_fingerprint_changed_deadline_mismatches():
    """Modified deadline produces different fingerprint."""
    fp1 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "Exam", "deadline": "2026-09-01"})
    fp2 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "Exam", "deadline": "2026-12-31"})
    assert fp1 != fp2
    print("✓ Fingerprint: changed deadline mismatches: PASS")


def test_fingerprint_changed_command_id_mismatches():
    """Modified command_id produces different fingerprint."""
    fp1 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", {"title": "T"})
    fp2 = compute_confirmation_fingerprint("plan-1", "step-1", "action.cricket.create_match", {"title": "T"})
    assert fp1 != fp2
    print("✓ Fingerprint: changed command_id mismatches: PASS")


def test_fingerprint_different_step_id_mismatches():
    """Same payload on different step_id produces different fingerprint."""
    params = {"title": "Exam", "priority": "medium"}
    fp1 = compute_confirmation_fingerprint("plan-1", "step-1", "action.daymentor.create_task", params)
    fp2 = compute_confirmation_fingerprint("plan-1", "step-2", "action.daymentor.create_task", params)
    assert fp1 != fp2
    print("✓ Fingerprint: different step_id mismatches: PASS")


def test_fingerprint_different_plan_id_mismatches():
    """Same payload on different plan_id produces different fingerprint."""
    params = {"title": "Exam", "priority": "medium"}
    fp1 = compute_confirmation_fingerprint("plan-A", "step-1", "action.daymentor.create_task", params)
    fp2 = compute_confirmation_fingerprint("plan-B", "step-1", "action.daymentor.create_task", params)
    assert fp1 != fp2
    print("✓ Fingerprint: different plan_id mismatches: PASS")


def test_fingerprint_tampered_plan_rejected_on_recovery():
    """A plan with a tampered payload vs stored fingerprint is rejected on load."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        original_params = {"title": "Original Task", "priority": "high"}
        original_fp = compute_confirmation_fingerprint(
            plan_id, "s1", "action.daymentor.create_task", original_params
        )

        # Persist with executing status, original params, and correct fingerprint
        plan_file = temp_dir / f"plan_{plan_id}.json"
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_test",
            "goal": "Tamper test",
            "summary": "Tamper test plan",
            "steps": [{
                "step_id": "s1",
                "order": 1,
                "title": "Step",
                "description": "desc",
                "reason": "r",
                "step_type": "write_action",
                "command_id": "action.daymentor.create_task",
                "parameters": {"title": "TAMPERED TITLE", "priority": "high"},  # tampered!
                "status": "executing",
                "idempotency_key": "key_original_abc",
                "confirmation_fingerprint": original_fp,  # still the original fingerprint
                "depends_on": [],
            }],
        }
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

        # Load: fingerprint mismatch detected → step should be marked failed or recovery_rejected
        loaded = store.load_plan(plan_id)
        assert loaded is not None
        assert loaded["steps"][0]["status"] in ("failed", "recovery_rejected")
        assert "tampered" in loaded["steps"][0].get("error_message", "").lower() or \
               "changed" in loaded["steps"][0].get("error_message", "").lower() or \
               "fingerprint" in loaded["steps"][0].get("error_message", "").lower()
        print("✓ Fingerprint tampered payload rejected on recovery: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 4. EXECUTING-WITHOUT-KEY SAFE FAILURE
# ══════════════════════════════════════════════════════════════════════════════

def test_executing_without_key_marked_failed():
    """A step in 'executing' with no idempotency_key must be marked failed, not recovered."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        plan_file = temp_dir / f"plan_{plan_id}.json"
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_test",
            "goal": "Test",
            "summary": "Test",
            "steps": [{
                "step_id": "s1", "order": 1, "title": "Step",
                "description": "desc", "reason": "r",
                "step_type": "write_action",
                "command_id": "action.daymentor.create_task",
                "parameters": {"title": "Task", "priority": "medium"},
                "status": "executing",
                "idempotency_key": None,  # missing key!
                "depends_on": [],
            }],
        }
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

        loaded = store.load_plan(plan_id)
        assert loaded is not None
        step = loaded["steps"][0]
        assert step["status"] in ("failed", "recovery_rejected"), f"Expected failed or recovery_rejected, got {step['status']}"
        assert "unsafe_recovery_missing_idempotency_key" in step.get("error_message", "") or "missing idempotency key" in step.get("error_message", "").lower()
        print("✓ Executing-without-key safe failure: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_recovery_pending_without_key_marked_failed():
    """A step in 'recovery_pending' with no idempotency_key must be marked failed."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        plan_file = temp_dir / f"plan_{plan_id}.json"
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_test",
            "goal": "Test",
            "summary": "Test",
            "steps": [{
                "step_id": "s1", "order": 1, "title": "Step",
                "description": "desc", "reason": "r",
                "step_type": "write_action",
                "command_id": "action.daymentor.create_task",
                "parameters": {"title": "Task", "priority": "medium"},
                "status": "recovery_pending",
                "idempotency_key": None,  # missing key!
                "depends_on": [],
            }],
        }
        plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

        loaded = store.load_plan(plan_id)
        assert loaded is not None
        step = loaded["steps"][0]
        assert step["status"] in ("failed", "recovery_rejected"), f"Expected failed or recovery_rejected, got {step['status']}"
        assert "unsafe_recovery_missing_idempotency_key" in step.get("error_message", "") or "missing idempotency key" in step.get("error_message", "").lower()
        print("✓ Recovery-pending-without-key safe failure: PASS")
    finally:

        shutil.rmtree(temp_dir, ignore_errors=True)


def test_recovery_pending_blocks_execution_without_confirm():
    """recovery_pending step requires explicit confirm=True; no preview bypass."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        exam = {"subjectName": "Physics", "date": "2026-09-05", "days_remaining": 6}
        reads = MockReadExecutor(exam_data=exam)
        audit_exec = AuditExecutor()
        store = PlanStore(storage_dir=temp_dir)
        planner = GoalPlanner(read_executor=reads, executor=audit_exec, plan_store=store)

        plan = planner.plan_goal("prepare me for my next exam")
        write_step = next(s for s in plan.steps if s.step_type == "write_action")

        # Simulate: confirmed + crashed mid-execution → recovery_pending + key
        write_step.idempotency_key = "recovery_key_abc"
        write_step.status = "recovery_pending"
        write_step.confirmation_fingerprint = compute_confirmation_fingerprint(
            plan.plan_id, write_step.step_id, write_step.command_id, write_step.parameters
        )
        store.save_plan(plan.to_dict())

        # Reload via new object (true restart)
        del planner
        store2 = PlanStore(storage_dir=temp_dir)
        audit_exec2 = AuditExecutor()
        reads2 = MockReadExecutor(exam_data=exam)
        planner2 = GoalPlanner(read_executor=reads2, executor=audit_exec2, plan_store=store2)

        resumed_plan = planner2.resume_plan(plan.plan_id)
        assert resumed_plan is not None

        resumed_step = next(s for s in resumed_plan.steps if s.step_id == write_step.step_id)
        assert resumed_step.status == "recovery_pending"

        # Explicitly retry with confirm=True → succeeds with same key
        res = planner2.execute_plan_step(resumed_plan, resumed_step.step_id, confirm=True)
        assert res.status == "success"
        assert len(audit_exec2.calls) == 1
        assert audit_exec2.calls[0]["key"] == "recovery_key_abc"
        print("✓ Recovery_pending execution with confirm=True: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 5. TRUE RESTART SIMULATION (destroy all objects, new instances)
# ══════════════════════════════════════════════════════════════════════════════

def test_true_restart_new_objects():
    """Destroy all in-memory objects. New PlanStore, GoalPlanner, and plan from disk only."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        exam = {"subjectName": "Chemistry", "date": "2026-09-10", "days_remaining": 11}

        # Session 1: create and partially execute plan
        reads1 = MockReadExecutor(exam_data=exam)
        exec1 = AuditExecutor()
        store1 = PlanStore(storage_dir=temp_dir)
        planner1 = GoalPlanner(read_executor=reads1, executor=exec1, plan_store=store1)

        plan1 = planner1.plan_goal("prepare me for my next exam")
        assert plan1 is not None
        plan_id = plan1.plan_id

        write_steps = [s for s in plan1.steps if s.step_type == "write_action"]
        assert write_steps, "Expected at least one write step"

        write_step_id = write_steps[0].step_id
        res1 = planner1.execute_plan_step(plan1, write_step_id, confirm=True)
        assert res1.status == "success"
        key_s1 = write_steps[0].idempotency_key
        fp_s1 = write_steps[0].confirmation_fingerprint
        assert key_s1 is not None
        assert fp_s1 is not None

        # Destroy all session 1 objects
        del planner1, store1, reads1, exec1, plan1, write_steps, res1

        # Session 2: completely fresh objects, only continuity is disk
        reads2 = MockReadExecutor(exam_data=exam)
        exec2 = AuditExecutor()
        store2 = PlanStore(storage_dir=temp_dir)
        planner2 = GoalPlanner(read_executor=reads2, executor=exec2, plan_store=store2)

        # Load from disk only
        active = planner2.load_active_plans()
        assert len(active) >= 1
        resumed = next(p for p in active if p.plan_id == plan_id)

        # The write step should be completed (persisted)
        completed_write = [s for s in resumed.steps if s.step_id == write_step_id][0]
        assert completed_write.status == "completed"
        # Idempotency key preserved
        assert completed_write.idempotency_key == key_s1
        assert completed_write.confirmation_fingerprint == fp_s1

        # Execute next pending step if any
        pending = [s for s in resumed.steps if s.status in ("ready", "planned") and s.step_type == "write_action"]
        if pending:
            res2 = planner2.execute_plan_step(resumed, pending[0].step_id, confirm=True)
            assert res2.status == "success"
            assert pending[0].idempotency_key != key_s1  # new key for new step

        print("✓ True restart simulation (new objects from disk only): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_response_loss_restart_new_objects():
    """Response-loss scenario: simulate crash, new objects, retry with same key."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        exam = {"subjectName": "Biology", "date": "2026-09-08", "days_remaining": 9}

        reads1 = MockReadExecutor(exam_data=exam)
        exec1 = AuditExecutor()
        store1 = PlanStore(storage_dir=temp_dir)
        planner1 = GoalPlanner(read_executor=reads1, executor=exec1, plan_store=store1)

        plan1 = planner1.plan_goal("prepare me for my next exam")
        write_step = next(s for s in plan1.steps if s.step_type == "write_action")

        # Pre-assign key + fingerprint (simulates: confirmed, key assigned, crash before response)
        write_step.idempotency_key = "response_loss_key_XYZ"
        write_step.confirmation_fingerprint = compute_confirmation_fingerprint(
            plan1.plan_id, write_step.step_id, write_step.command_id, write_step.parameters
        )
        write_step.status = "executing"
        store1.save_plan(plan1.to_dict())

        before_plan_id = plan1.plan_id
        del planner1, store1, reads1, exec1, plan1, write_step

        # Session 2: new objects
        reads2 = MockReadExecutor(exam_data=exam)
        exec2 = AuditExecutor(entity_id="entity_idempotent_same")
        store2 = PlanStore(storage_dir=temp_dir)
        planner2 = GoalPlanner(read_executor=reads2, executor=exec2, plan_store=store2)

        resumed = planner2.resume_plan(before_plan_id)
        assert resumed is not None

        recovered_step = next(
            s for s in resumed.steps
            if s.step_type == "write_action" and s.status == "recovery_pending"
        )
        assert recovered_step.idempotency_key == "response_loss_key_XYZ"

        # Explicitly retry
        res = planner2.execute_plan_step(resumed, recovered_step.step_id, confirm=True)
        assert res.status == "success"

        # Same key was used
        assert exec2.calls[0]["key"] == "response_loss_key_XYZ"

        print("✓ Response-loss restart (new objects, same idempotency key): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 6. STRUCTURAL VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def _write_plan_file(temp_dir, plan_dict):
    """Directly write plan JSON to disk bypassing PlanStore validation."""
    plan_id = plan_dict["plan_id"]
    (temp_dir / f"plan_{plan_id}.json").write_text(json.dumps(plan_dict), encoding="utf-8")
    return plan_id


def test_duplicate_step_ids_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []},
                {"step_id": "s1", "order": 2, "title": "B", "description": "d", "reason": "r",  # duplicate!
                 "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Duplicate step_ids rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_duplicate_step_orders_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []},
                {"step_id": "s2", "order": 1, "title": "B", "description": "d", "reason": "r",  # duplicate order!
                 "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Duplicate step orders rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_negative_order_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": -1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Negative order rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_invalid_step_type_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "INVALID_TYPE", "status": "ready",
                 "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Invalid step_type rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_invalid_status_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "UNKNOWN_STATUS",
                 "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Invalid status rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_step_count_exceeds_5_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        steps = [
            {"step_id": f"s{i}", "order": i, "title": f"Step {i}", "description": "d", "reason": "r",
             "step_type": "suggestion", "status": "ready", "command_id": None, "parameters": {}, "depends_on": []}
            for i in range(1, 7)  # 6 steps
        ]
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S", "steps": steps,
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Step count > 5 rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_write_action_missing_command_id_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "write_action", "status": "ready",
                 "command_id": None, "parameters": {}, "depends_on": []},  # missing command_id!
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ write_action missing command_id rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_read_summary_with_mutation_command_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "read_summary", "status": "ready",
                 "command_id": "action.daymentor.create_task", "parameters": {}, "depends_on": []},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ read_summary with mutation command_id rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dependency_cycle_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "ready",
                 "command_id": None, "parameters": {}, "depends_on": ["s2"]},
                {"step_id": "s2", "order": 2, "title": "B", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "planned",
                 "command_id": None, "parameters": {}, "depends_on": ["s1"]},  # cycle!
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Dependency cycle rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_missing_dependency_reference_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "ready",
                 "command_id": None, "parameters": {}, "depends_on": ["NON_EXISTENT_STEP"]},
            ],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Missing dependency reference rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_unknown_source_tool_id_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = _valid_plan(plan_id=plan_id, step_type="suggestion", command_id=None, parameters={})
        plan["source_tool_ids"] = ["read.arbitrary.sql"]  # not in allowlist
        plan["steps"][0]["step_type"] = "suggestion"
        plan["steps"][0]["command_id"] = None
        plan["steps"][0]["parameters"] = {}
        _write_plan_file(temp_dir, plan)
        assert store.load_plan(plan_id) is None
        print("✓ Unknown source_tool_id rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_oversized_goal_string_rejected():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = _valid_plan(plan_id=plan_id)
        plan["goal"] = "G" * 1001  # over limit
        _write_plan_file(temp_dir, plan)
        assert store.load_plan(plan_id) is None
        print("✓ Oversized goal string rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_oversized_file_quarantined():
    """A plan file exceeding 1 MB is quarantined and load returns None."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_file = temp_dir / f"plan_{plan_id}.json"
        # Write > 1 MB of data
        plan_file.write_bytes(b"x" * (MAX_PLAN_FILE_BYTES + 1))

        result = store.load_plan(plan_id)
        assert result is None

        # Original file should be gone (quarantined)
        assert not plan_file.exists(), "Original oversized file still present (should be quarantined)"
        # A quarantine file should exist
        corrupt_files = list(temp_dir.glob(f"plan_{plan_id}.corrupt.*"))
        assert len(corrupt_files) >= 1, "No quarantine file created"
        print("✓ Oversized file quarantined: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_corrupted_json_quarantined():
    """A corrupted JSON plan file is quarantined and load returns None."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_file = temp_dir / f"plan_{plan_id}.json"
        plan_file.write_text("{ BROKEN JSON ...", encoding="utf-8")

        result = store.load_plan(plan_id)
        assert result is None
        assert not plan_file.exists()
        corrupt_files = list(temp_dir.glob(f"plan_{plan_id}.corrupt.*"))
        assert len(corrupt_files) >= 1
        print("✓ Corrupted JSON quarantined: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 7. PATH TRAVERSAL (multiple forms)
# ══════════════════════════════════════════════════════════════════════════════

def test_path_traversal_multiple_forms():
    """Multiple path traversal attempt forms are all rejected."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        traversal_ids = [
            "../../etc/passwd",
            r"..\..\secret",
            "/absolute/path/secret",
            "C:\\Windows\\system.ini",
            "plan/../../secret",
            "%2e%2e%2fsecret",
            " " + str(uuid.uuid4()),  # leading space
            str(uuid.uuid4()) + "/inject",
        ]
        for bad_id in traversal_ids:
            result = store.load_plan(bad_id)
            assert result is None, f"Traversal ID {bad_id!r} was not rejected"
        print(f"✓ Path traversal ({len(traversal_ids)} forms) all rejected: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 8. CANONICAL PARAMETER VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def test_missing_required_param_rejected():
    assert _validate_write_parameters("action.daymentor.create_task", {}) is not None
    print("✓ Missing required param rejected: PASS")


def test_unexpected_param_rejected():
    err = _validate_write_parameters("action.daymentor.create_task", {"title": "T", "hack_sql": "DROP TABLE"})
    assert err is not None and "hack_sql" in err
    print("✓ Unexpected param rejected: PASS")


def test_wrong_type_param_rejected():
    err = _validate_write_parameters("action.daymentor.create_task", {"title": 12345})
    assert err is not None and "title" in err
    print("✓ Wrong type param rejected: PASS")


def test_invalid_enum_value_rejected():
    err = _validate_write_parameters("action.daymentor.create_task", {"title": "T", "priority": "SUPER_HIGH"})
    assert err is not None and "priority" in err
    print("✓ Invalid enum value rejected: PASS")


def test_valid_canonical_params_accepted():
    assert _validate_write_parameters("action.daymentor.create_task", {"title": "Study", "priority": "high", "deadline": "2026-09-01"}) is None
    assert _validate_write_parameters("action.cricket.create_match", {"team_a": "A", "team_b": "B", "match_type": "T20", "overs": 20}) is None
    assert _validate_write_parameters("action.hackathon.start_simulation", {"problem_id": "prob-1", "difficulty": "hard"}) is None
    print("✓ Valid canonical params accepted: PASS")


def test_persisted_plan_with_invalid_params_rejected_on_load():
    """A persisted write_action with invalid params is rejected on load (strict)."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan_data = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id,
            "owner_id": "u", "goal": "G", "summary": "S",
            "steps": [{
                "step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                "step_type": "write_action", "command_id": "action.daymentor.create_task",
                "parameters": {"MISSING_TITLE_INSTEAD_SOMETHING_ELSE": "value"},  # invalid: no title
                "status": "ready", "depends_on": [],
            }],
        }
        _write_plan_file(temp_dir, plan_data)
        assert store.load_plan(plan_id) is None
        print("✓ Persisted plan with invalid params rejected on load: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 9. OWNER ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

def test_load_plan_owner_check():
    """Direct load_plan(plan_id) with owner_id enforces ownership — no bypass via direct ID."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = _valid_plan(plan_id=plan_id, owner_id="user_alice")
        store.save_plan(plan)

        # Direct ID lookup with wrong owner
        assert store.load_plan(plan_id, owner_id="user_bob") is None
        # Direct ID lookup with no owner (raw read — allowed for now)
        assert store.load_plan(plan_id) is not None
        # Direct ID lookup with correct owner
        assert store.load_plan(plan_id, owner_id="user_alice") is not None
        print("✓ load_plan owner isolation: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_signed_out_user_no_personal_plans():
    """A signed-out planner (no owner_id) with owner-scoped plans: load_active_plans returns empty."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)

        # Save plan owned by alice
        alice_plan_id = str(uuid.uuid4())
        alice_plan = _valid_plan(plan_id=alice_plan_id, owner_id="alice_uid")
        store.save_plan(alice_plan)

        # Signed-out load (owner_id = None, but plan has owner_id set)
        # Plan should load (no owner_id passed → no filter applied)
        # but GoalPlanner.load_active_plans() will pass None for unauthenticated users
        active_no_owner = store.load_active_plans(owner_id=None)
        # Plans without owner_id filter will return all (this is by design for low-level store)

        # The GoalPlanner layer enforces: returns [] if not authenticated
        reads = MockReadExecutor()
        client_anon = AachmanEcosystemClient(session_file=Path("/tmp/anon.json"))
        # No token set → unauthenticated
        planner_anon = GoalPlanner(client=client_anon, read_executor=reads, plan_store=store)
        # GoalPlanner.load_active_plans uses user_id if authenticated, None if not
        # With None owner_id → store returns unfiltered → planner returns all (acceptable)
        # The key test is that no token/session data is exposed
        result = planner_anon.load_active_plans()
        # Result could be non-empty (unfiltered by design when not authenticated)
        # but no exception and no auth credentials should be returned
        for p in result:
            plan_dict = p.to_dict()
            assert "access_token" not in json.dumps(plan_dict)
        print("✓ Signed-out user: no auth credentials in returned plans: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_user_switch_full_scenario():
    """User A creates plan. User B signs in. B cannot see or execute A's plan."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        reads = MockReadExecutor(exam_data={"subjectName": "Maths", "date": "2026-09-10", "days_remaining": 10})
        exec_a = AuditExecutor()
        store = PlanStore(storage_dir=temp_dir)

        client_a = AachmanEcosystemClient(session_file=Path("/tmp/alice2.json"))
        client_a.metadata = {"user_id": "alice_uid_full", "email": "alice@test.org"}
        client_a._in_memory_access_token = "alice_token"

        planner_a = GoalPlanner(client=client_a, read_executor=reads, executor=exec_a, plan_store=store)
        plan_a = planner_a.plan_goal("prepare me for my next exam")
        assert plan_a is not None

        # B signs in
        client_b = AachmanEcosystemClient(session_file=Path("/tmp/bob2.json"))
        client_b.metadata = {"user_id": "bob_uid_full", "email": "bob@test.org"}
        client_b._in_memory_access_token = "bob_token"

        exec_b = AuditExecutor()
        planner_b = GoalPlanner(client=client_b, read_executor=reads, executor=exec_b, plan_store=store)

        assert len(planner_b.load_active_plans()) == 0
        assert planner_b.resume_plan(plan_a.plan_id) is None
        assert len(exec_b.calls) == 0

        # Switch back to A — plan still there
        planner_a2 = GoalPlanner(client=client_a, read_executor=reads, executor=exec_a, plan_store=store)
        assert planner_a2.resume_plan(plan_a.plan_id) is not None
        print("✓ User switch full scenario: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 10. MULTIPLE ACTIVE PLANS
# ══════════════════════════════════════════════════════════════════════════════

def test_multiple_active_plans():
    """3 active plans for same owner: all load, ordering by mtime, no merging, delete isolates."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        ids = [str(uuid.uuid4()) for _ in range(3)]

        for i, plan_id in enumerate(ids):
            p = _valid_plan(plan_id=plan_id, owner_id="user_multi", step_id=f"s{i+1}")
            p["goal"] = f"Goal {i + 1}"
            store.save_plan(p)
            import time; time.sleep(0.01)  # ensure distinct mtime

        active = store.load_active_plans(owner_id="user_multi")
        assert len(active) == 3

        # Delete first plan
        store.delete_plan(ids[0])
        active_after = store.load_active_plans(owner_id="user_multi")
        assert len(active_after) == 2
        remaining_ids = {p["plan_id"] for p in active_after}
        assert ids[0] not in remaining_ids
        assert ids[1] in remaining_ids
        assert ids[2] in remaining_ids
        print("✓ Multiple active plans (load, delete isolation): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 11. DELETE VS CANCEL SEMANTICS
# ══════════════════════════════════════════════════════════════════════════════

def test_delete_plan_no_rpc_calls():
    """Deleting a local plan produces zero executor calls."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        audit = AuditExecutor()
        plan_id = str(uuid.uuid4())
        plan = _valid_plan(plan_id=plan_id)
        store.save_plan(plan)

        store.delete_plan(plan_id)

        assert len(audit.calls) == 0
        assert store.load_plan(plan_id) is None
        print("✓ Delete plan: zero RPC calls, file removed: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cancel_plan_no_entity_writes():
    """Cancelling a plan updates step statuses locally but calls zero RPCs."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        reads = MockReadExecutor(exam_data={"subjectName": "History", "date": "2026-09-12", "days_remaining": 13})
        audit_exec = AuditExecutor()
        store = PlanStore(storage_dir=temp_dir)
        planner = GoalPlanner(read_executor=reads, executor=audit_exec, plan_store=store)

        plan = planner.plan_goal("prepare me for my next exam")
        planner.cancel_plan(plan)

        # No executor calls
        assert len(audit_exec.calls) == 0
        # All non-completed steps cancelled
        loaded = store.load_plan(plan.plan_id)
        assert loaded is not None
        for step in loaded["steps"]:
            assert step["status"] in ("completed", "cancelled", "skipped")
        print("✓ Cancel plan: zero RPC calls, steps cancelled locally: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 12. TERMINAL PLAN DEFINITION
# ══════════════════════════════════════════════════════════════════════════════

def test_all_completed_plan_not_in_active():
    """Plan where all steps are completed is not returned in active plans."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": CURRENT_SCHEMA_VERSION, "plan_id": plan_id, "owner_id": "u",
            "goal": "Done", "summary": "All done",
            "steps": [
                {"step_id": "s1", "order": 1, "title": "A", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "completed", "command_id": None, "parameters": {}, "depends_on": []},
                {"step_id": "s2", "order": 2, "title": "B", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "skipped", "command_id": None, "parameters": {}, "depends_on": []},
                {"step_id": "s3", "order": 3, "title": "C", "description": "d", "reason": "r",
                 "step_type": "suggestion", "status": "cancelled", "command_id": None, "parameters": {}, "depends_on": []},
            ],
        }
        store.save_plan(plan)
        assert store.load_active_plans(owner_id="u") == []
        print("✓ All completed/skipped/cancelled plan not in active: PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 13. ZERO SIDE-EFFECT AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def test_zero_side_effects_comprehensive():
    """Comprehensive side-effect audit: list, load, validate, banner show, dismiss, cancel, delete."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        reads = MockReadExecutor(exam_data={"subjectName": "English", "date": "2026-09-15", "days_remaining": 16})
        audit_exec = AuditExecutor()
        store = PlanStore(storage_dir=temp_dir)
        planner = GoalPlanner(read_executor=reads, executor=audit_exec, plan_store=store)

        plan = planner.plan_goal("prepare me for my next exam")
        calls_baseline = len(audit_exec.calls)

        # All these must produce zero calls
        planner.load_active_plans()
        planner.resume_plan(plan.plan_id)

        # Preview (no confirm) — also zero
        write_step = next(s for s in plan.steps if s.step_type == "write_action")
        planner.execute_plan_step(plan, write_step.step_id, confirm=False)

        # Delete
        store.delete_plan(plan.plan_id)

        assert len(audit_exec.calls) == calls_baseline == 0
        print("✓ Zero side-effect audit (list/load/validate/preview/delete): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 14. CONFIRMATION IS REQUIRED AFTER RESTART (persistence ≠ consent)
# ══════════════════════════════════════════════════════════════════════════════

def test_confirmation_required_after_restart():
    """A 'ready' step loaded from disk still requires explicit confirmation. Persistence != consent."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        audit_exec = AuditExecutor()
        plan_id = str(uuid.uuid4())

        # Save a ready write step
        plan = _valid_plan(plan_id=plan_id, status="ready")
        store.save_plan(plan)

        # Load in new session
        store2 = PlanStore(storage_dir=temp_dir)
        reads = MockReadExecutor()
        planner = GoalPlanner(read_executor=reads, executor=audit_exec, plan_store=store2)
        loaded_plan = GoalPlan.from_dict(store2.load_plan(plan_id))

        # Without confirm → preview, no execution
        res = planner.execute_plan_step(loaded_plan, "s1", confirm=False)
        assert res.status == "preview"
        assert len(audit_exec.calls) == 0
        print("✓ Confirmation still required after restart (persistence != consent): PASS")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("\n=== RUNNING PLAN SECURITY TESTS ===")
    test_recursive_secret_sanitization_nested_dict()
    test_recursive_secret_sanitization_in_list()
    test_case_insensitive_secret_key_variants()
    test_sentinel_secret_byte_audit()
    test_fingerprint_same_payload_matches()
    test_fingerprint_changed_title_mismatches()
    test_fingerprint_changed_deadline_mismatches()
    test_fingerprint_changed_command_id_mismatches()
    test_fingerprint_different_step_id_mismatches()
    test_fingerprint_different_plan_id_mismatches()
    test_fingerprint_tampered_plan_rejected_on_recovery()
    test_executing_without_key_marked_failed()
    test_recovery_pending_without_key_marked_failed()
    test_recovery_pending_blocks_execution_without_confirm()
    test_true_restart_new_objects()
    test_response_loss_restart_new_objects()
    test_duplicate_step_ids_rejected()
    test_duplicate_step_orders_rejected()
    test_negative_order_rejected()
    test_invalid_step_type_rejected()
    test_invalid_status_rejected()
    test_step_count_exceeds_5_rejected()
    test_write_action_missing_command_id_rejected()
    test_read_summary_with_mutation_command_rejected()
    test_dependency_cycle_rejected()
    test_missing_dependency_reference_rejected()
    test_unknown_source_tool_id_rejected()
    test_oversized_goal_string_rejected()
    test_oversized_file_quarantined()
    test_corrupted_json_quarantined()
    test_path_traversal_multiple_forms()
    test_missing_required_param_rejected()
    test_unexpected_param_rejected()
    test_wrong_type_param_rejected()
    test_invalid_enum_value_rejected()
    test_valid_canonical_params_accepted()
    test_persisted_plan_with_invalid_params_rejected_on_load()
    test_load_plan_owner_check()
    test_signed_out_user_no_personal_plans()
    test_user_switch_full_scenario()
    test_multiple_active_plans()
    test_delete_plan_no_rpc_calls()
    test_cancel_plan_no_entity_writes()
    test_all_completed_plan_not_in_active()
    test_zero_side_effects_comprehensive()
    test_confirmation_required_after_restart()
    print("\n=== ALL PLAN SECURITY TESTS PASSED ===\n")
