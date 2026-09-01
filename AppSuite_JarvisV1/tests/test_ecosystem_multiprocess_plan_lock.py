"""Real Windows cross-process PlanLock and multi-process confirmation tests.

Uses actual OS subprocesses on Windows to verify:
1. Mutual exclusion: Process A holds lock; Process B receives PlanLockTimeoutError.
2. Sequential handoff: Once Process A releases lock, Process B successfully acquires lock.
3. Stale lock recovery: Pre-existing .lock file from dead process is acquired without error.
4. Multi-process key assignment: Two processes confirming same step yield exactly 1 distinct idempotency key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import pytest

from appsuite.ecosystem.goal_planner import GoalPlan, GoalPlanner, GoalPlanStep
from appsuite.ecosystem.plan_store import PlanLock, PlanLockTimeoutError, PlanStore


@pytest.fixture
def temp_store_dir():
    d = tempfile.mkdtemp(prefix="pyflare_mp_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_real_windows_cross_process_plan_lock_mutual_exclusion(temp_store_dir):
    """Verify that two real Windows OS processes cannot simultaneously hold PlanLock on the same plan."""
    plan_id = str(uuid.uuid4())
    lock_file = temp_store_dir / f"plan_{plan_id}.lock"

    # Script for Process A: acquires lock, writes 'acquired', sleeps 2s, writes 'releasing'
    proc_a_code = f"""
import sys, time, pathlib
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")
from appsuite.ecosystem.plan_store import PlanLock

storage_dir = pathlib.Path(r"{temp_store_dir}")
plan_id = "{plan_id}"

with PlanLock(plan_id, storage_dir=storage_dir, timeout=5.0):
    print("PROC_A_ACQUIRED", flush=True)
    time.sleep(1.5)
    print("PROC_A_RELEASING", flush=True)
"""

    # Script for Process B: attempts lock with short timeout
    proc_b_code = f"""
import sys, time, pathlib
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")
from appsuite.ecosystem.plan_store import PlanLock, PlanLockTimeoutError

storage_dir = pathlib.Path(r"{temp_store_dir}")
plan_id = "{plan_id}"

try:
    with PlanLock(plan_id, storage_dir=storage_dir, timeout=0.4):
        print("PROC_B_ACQUIRED_UNEXPECTEDLY", flush=True)
except PlanLockTimeoutError:
    print("PROC_B_TIMEOUT_CONFIRMED", flush=True)
"""

    # Script for Process C: attempts lock with 3s timeout (should succeed after Process A finishes)
    proc_c_code = f"""
import sys, time, pathlib
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")
from appsuite.ecosystem.plan_store import PlanLock

storage_dir = pathlib.Path(r"{temp_store_dir}")
plan_id = "{plan_id}"

with PlanLock(plan_id, storage_dir=storage_dir, timeout=4.0):
    print("PROC_C_ACQUIRED_SUCCESS", flush=True)
"""

    # 1. Start Process A
    proc_a = subprocess.Popen(
        [sys.executable, "-c", proc_a_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for Process A to signal it acquired the lock
    line = proc_a.stdout.readline()
    assert "PROC_A_ACQUIRED" in line, f"Process A failed to acquire lock: {line}"

    # 2. Start Process B while Process A is holding lock -> Must timeout
    proc_b = subprocess.run(
        [sys.executable, "-c", proc_b_code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert "PROC_B_TIMEOUT_CONFIRMED" in proc_b.stdout, f"Process B did not timeout! Output: {proc_b.stdout}"

    # 3. Start Process C with enough timeout to wait for Process A to exit
    proc_c = subprocess.run(
        [sys.executable, "-c", proc_c_code],
        capture_output=True,
        text=True,
        timeout=6,
    )
    assert "PROC_C_ACQUIRED_SUCCESS" in proc_c.stdout, f"Process C failed: {proc_c.stdout}"

    proc_a.communicate(timeout=5)
    assert proc_a.returncode == 0


def test_stale_lock_file_acquired_by_new_process(temp_store_dir):
    """Verify that an abandoned .lock file on disk does not block a new process if OS lock is released."""
    plan_id = str(uuid.uuid4())
    lock_file = temp_store_dir / f"plan_{plan_id}.lock"

    # Create dummy stale lock file
    lock_file.write_text("12345", encoding="utf-8")

    # Acquire lock with a real process
    proc_code = f"""
import sys, pathlib
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")
from appsuite.ecosystem.plan_store import PlanLock

storage_dir = pathlib.Path(r"{temp_store_dir}")
plan_id = "{plan_id}"

with PlanLock(plan_id, storage_dir=storage_dir, timeout=2.0):
    print("STALE_LOCK_ACQUIRED_OK", flush=True)
"""

    res = subprocess.run(
        [sys.executable, "-c", proc_code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert res.returncode == 0
    assert "STALE_LOCK_ACQUIRED_OK" in res.stdout


def test_two_process_single_key_assignment(temp_store_dir):
    """Two separate OS processes attempting explicit confirmation on the same step must coordinate and yield 1 distinct key."""
    plan_id = str(uuid.uuid4())
    owner_id = "user_mp_test_99"

    plan = GoalPlan(
        goal="Multi-Process Coordination Goal",
        summary="Plan for two-process test",
        source_tool_ids=["read.daymentor.tasks_today"],
        plan_id=plan_id,
        owner_id=owner_id,
        confidence=1.0,
        steps=[
            GoalPlanStep(
                step_id="step_write_01",
                order=1,
                title="Create Physics Task",
                description="Study session",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Physics revision", "priority": "high", "deadline": "2026-09-05"},
                status="ready",
            )
        ],
    )
    store = PlanStore(storage_dir=temp_store_dir)
    store.save_plan(plan.to_dict())

    # Script executed by both processes concurrently
    runner_code = f"""
import sys, pathlib, json
from unittest.mock import MagicMock
sys.path.insert(0, r"{Path(__file__).resolve().parent.parent}")

from appsuite.ecosystem.goal_planner import GoalPlanner, GoalPlan
from appsuite.ecosystem.plan_store import PlanStore
from appsuite.ecosystem.executor import EcosystemExecutor, ExecutionResult
from appsuite.ecosystem.client import AachmanEcosystemClient

storage_dir = pathlib.Path(r"{temp_store_dir}")
plan_id = "{plan_id}"
owner_id = "{owner_id}"

client = MagicMock(spec=AachmanEcosystemClient)
client.is_authenticated = True
client.user_id = owner_id

executor = MagicMock(spec=EcosystemExecutor)
executor.execute_intent.return_value = ExecutionResult(
    command_id="action.daymentor.create_task",
    status="success",
    message="Task created",
    preview_data={{"entity_id": "task_123"}},
)

store = PlanStore(storage_dir=storage_dir)
planner = GoalPlanner(client=client, executor=executor, plan_store=store)

plan = planner.resume_plan(plan_id)
res = planner.execute_plan_step(plan, "step_write_01", confirm=True)

# Print observed step key
loaded = store.load_plan(plan_id, owner_id=owner_id)
step = loaded["steps"][0]
print(f"RESULT_KEY:{{step.get('idempotency_key')}}", flush=True)
"""

    p1 = subprocess.Popen([sys.executable, "-c", runner_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen([sys.executable, "-c", runner_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    assert p1.returncode == 0, f"Process 1 error: {err1}"
    assert p2.returncode == 0, f"Process 2 error: {err2}"

    key1 = None
    for line in out1.splitlines():
        if line.startswith("RESULT_KEY:"):
            key1 = line.split(":", 1)[1].strip()

    key2 = None
    for line in out2.splitlines():
        if line.startswith("RESULT_KEY:"):
            key2 = line.split(":", 1)[1].strip()

    assert key1 is not None and len(key1) > 0, f"Process 1 returned empty key! Output: {out1}"
    assert key2 is not None and len(key2) > 0, f"Process 2 returned empty key! Output: {out2}"
    assert key1 == key2, f"Processes generated distinct keys! Key1: {key1}, Key2: {key2}"

    # Verify authoritative disk state has exactly 1 key
    final_plan = store.load_plan(plan_id, owner_id=owner_id)
    assert final_plan["steps"][0]["idempotency_key"] == key1
    assert final_plan["steps"][0]["status"] == "completed"
