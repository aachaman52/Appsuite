"""Unit Tests for Jarvis PlanStore v1."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

# Ensure AppSuite_JarvisV1 root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from appsuite.ecosystem import (
    PlanStore,
    GoalPlan,
    GoalPlanStep,
    CURRENT_SCHEMA_VERSION,
)


def test_save_and_load_plan_roundtrip():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        step_id = str(uuid.uuid4())[:8]

        sample_plan = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "user_12345",
            "goal": "Prepare for Mathematics Exam",
            "summary": "3-step exam study plan",
            "source_tool_ids": ["read.daymentor.next_exam"],
            "confidence": 1.0,
            "steps": [
                {
                    "step_id": step_id,
                    "order": 1,
                    "title": "Mathematics revision",
                    "description": "Core concepts review",
                    "step_type": "write_action",
                    "command_id": "action.daymentor.create_task",
                    "parameters": {"title": "Maths revision", "priority": "high"},
                    "requires_confirmation": True,
                    "status": "ready",
                    "depends_on": [],
                    "idempotency_key": "idemp_key_abc123",
                }
            ],
        }

        saved_id = store.save_plan(sample_plan)
        assert saved_id == plan_id

        loaded = store.load_plan(plan_id, owner_id="user_12345")
        assert loaded is not None
        assert loaded["plan_id"] == plan_id
        assert loaded["owner_id"] == "user_12345"
        assert loaded["steps"][0]["idempotency_key"] == "idemp_key_abc123"
        print("✓ Roundtrip save and load test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_atomic_overwrite():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        plan = {
            "plan_id": plan_id,
            "goal": "Test Goal",
            "steps": [{"step_id": "s1", "order": 1, "title": "Step 1", "step_type": "suggestion", "status": "ready"}],
        }
        store.save_plan(plan)

        # Update step status
        plan["steps"][0]["status"] = "completed"
        store.save_plan(plan)

        loaded = store.load_plan(plan_id)
        assert loaded["steps"][0]["status"] == "completed"
        # Verify no orphaned temp files
        tmp_files = list(temp_dir.glob("tmp_plan_*"))
        assert len(tmp_files) == 0
        print("✓ Atomic overwrite test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_completed_plan_excluded_from_active():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        completed_plan = {
            "plan_id": plan_id,
            "owner_id": "user_123",
            "goal": "Completed Goal",
            "steps": [{"step_id": "s1", "order": 1, "title": "Step 1", "step_type": "suggestion", "status": "completed"}],
        }
        store.save_plan(completed_plan)

        active = store.load_active_plans(owner_id="user_123")
        assert len(active) == 0
        print("✓ Completed plans excluded from active test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_corrupted_json_and_unsupported_schema():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        bad_plan_id = str(uuid.uuid4())

        # 1. Corrupted file
        corrupt_file = temp_dir / f"plan_{bad_plan_id}.json"
        corrupt_file.write_text("{ broken json ...", encoding="utf-8")
        assert store.load_plan(bad_plan_id) is None

        # 2. Unsupported schema version
        future_plan_id = str(uuid.uuid4())
        future_file = temp_dir / f"plan_{future_plan_id}.json"
        future_file.write_text(json.dumps({"schema_version": 99, "plan_id": future_plan_id, "steps": []}), encoding="utf-8")
        assert store.load_plan(future_plan_id) is None

        # Active plans loader ignores both safely without crashing
        assert len(store.load_active_plans()) == 0
        print("✓ Corrupted JSON and unsupported schema test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_malicious_command_id_and_path_traversal():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)

        # 1. Malicious command ID
        bad_id = str(uuid.uuid4())
        malicious_plan = {
            "plan_id": bad_id,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "goal": "Exploit",
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": "Exploit",
                    "step_type": "write_action",
                    "command_id": "action.admin.delete_all",
                    "status": "ready",
                }
            ],
        }
        store.save_plan(malicious_plan)
        assert store.load_plan(bad_id) is None

        # 2. Path traversal in plan_id
        assert store.load_plan("../../etc/passwd") is None
        print("✓ Malicious command ID and path traversal rejection test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_owner_isolation_and_no_secret_leakage():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        plan = {
            "plan_id": plan_id,
            "owner_id": "user_alice",
            "goal": "Alice Goal",
            "access_token": "secret_token_12345",
            "jwt": "header.payload.sig",
            "password": "my_password",
            "steps": [{"step_id": "s1", "order": 1, "title": "Step 1", "step_type": "suggestion", "status": "ready"}],
        }
        store.save_plan(plan)

        # User Bob cannot load User Alice's plan
        assert store.load_plan(plan_id, owner_id="user_bob") is None
        # User Alice can load her plan
        loaded = store.load_plan(plan_id, owner_id="user_alice")
        assert loaded is not None

        # Verify raw file contains zero auth tokens
        raw_text = (temp_dir / f"plan_{plan_id}.json").read_text(encoding="utf-8")
        assert "secret_token_12345" not in raw_text
        assert "header.payload.sig" not in raw_text
        assert "my_password" not in raw_text
        print("✓ Owner isolation and secret stripping test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_executing_step_recovery_on_startup():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())

        # Plan saved while step was mid-execution (has key, no fingerprint = legacy plan)
        plan = {
            "plan_id": plan_id,
            "goal": "Interrupted Goal",
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": "Interrupted Step",
                    "description": "Create revision task",
                    "step_type": "write_action",
                    "command_id": "action.daymentor.create_task",
                    "parameters": {"title": "Interrupted Revision Task", "priority": "high"},
                    "status": "executing",
                    "idempotency_key": "in_flight_key_999",
                    "depends_on": [],
                    "reason": "Interrupted mid-execution",
                }
            ],
        }
        store.save_plan(plan)

        # On restart / load:
        # executing + key + no fingerprint (legacy) -> recovery_pending
        # idempotency_key preserved
        loaded = store.load_plan(plan_id)
        assert loaded is not None, "Plan should load successfully"
        assert loaded["steps"][0]["status"] == "recovery_pending", (
            f"Expected recovery_pending, got {loaded['steps'][0]['status']}"
        )
        assert loaded["steps"][0]["idempotency_key"] == "in_flight_key_999"
        print("✓ Executing step recovery test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



def test_delete_and_archive_plan():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        plan_id = str(uuid.uuid4())
        plan = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "plan_id": plan_id,
            "owner_id": "u1",
            "goal": "Goal",
            "summary": "Summary",
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": "Step 1",
                    "description": "d",
                    "reason": "r",
                    "step_type": "suggestion",
                    "status": "ready",
                    "depends_on": [],
                }
            ],
        }
        store.save_plan(plan)
        assert store.load_plan(plan_id) is not None

        # Archive marks unexecuted steps as cancelled
        assert store.archive_plan(plan_id) is True
        loaded = store.load_plan(plan_id)
        assert loaded["steps"][0]["status"] == "cancelled"

        # Delete removes file
        assert store.delete_plan(plan_id) is True
        assert store.load_plan(plan_id) is None
        print("✓ Delete and archive plan test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("\n=== RUNNING PLAN STORE TESTS ===")
    test_save_and_load_plan_roundtrip()
    test_atomic_overwrite()
    test_completed_plan_excluded_from_active()
    test_corrupted_json_and_unsupported_schema()
    test_malicious_command_id_and_path_traversal()
    test_owner_isolation_and_no_secret_leakage()
    test_executing_step_recovery_on_startup()
    test_delete_and_archive_plan()
    print("\n=== ALL PLAN STORE TESTS PASSED ===\n")

