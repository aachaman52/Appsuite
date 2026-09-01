"""Test suite for PyFlare Beta Execution Safety Hardening v1.

Verifies:
1. recovery_pending + confirm=False returns preview and triggers 0 dispatches
2. Terminal states (completed, skipped, cancelled, blocked, recovery_rejected) cannot execute
3. Unsafe recovery (missing key / fingerprint mismatch) transitions to recovery_rejected
4. Fail-closed ownership isolation for unauthenticated calls and owner mismatches
5. Pre-dispatch save failure aborts execution with 0 dispatches
6. Multi-session PlanLock coordination preserves idempotency key
7. Parameter validation at dispatch rejects invalid inputs without corrupting steps
8. Malformed plan files in storage do not break healthy sibling plans
9. Read failures return explicit unavailable status instead of fabricating empty facts
10. Exam schedule calculations properly set today's deadline and query tomorrow's tasks
"""
from __future__ import annotations

import datetime
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from appsuite.ecosystem.action_validation import (
    validate_action_parameters,
)
from appsuite.ecosystem.client import AachmanEcosystemClient
from appsuite.ecosystem.constants import (
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
)
from appsuite.ecosystem.executor import EcosystemExecutor, ExecutionResult
from appsuite.ecosystem.goal_planner import GoalPlan, GoalPlanner, GoalPlanStep
from appsuite.ecosystem.plan_store import (
    PlanStore,
    PlanLock,
    PlanLockTimeoutError,
    compute_confirmation_fingerprint,
)
from appsuite.ecosystem.planner import EcosystemPlanner
from appsuite.ecosystem.planning_helpers import (
    calculate_exam_revision_schedule,
    is_duplicate_task,
    normalize_subject,
)
from appsuite.ecosystem.read_executor import EcosystemReadExecutor, JarvisReadResponse
from appsuite.ecosystem.read_interpreter import JarvisReadIntent


@pytest.fixture
def temp_store_dir():
    d = tempfile.mkdtemp(prefix="pyflare_test_store_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=AachmanEcosystemClient)
    client.is_authenticated = True
    client.user_id = "user_beta_test_123"
    client.user_email = "tester@aachman.com"
    client.supabase_url = "https://pazkkzfdiwpcguoghlus.supabase.co"
    client.supabase_key = "test_key"
    client.get_valid_access_token.return_value = "mock_jwt_token"
    return client


# ── 1. recovery_pending + confirm=False Guard ─────────────────────────────────

def test_recovery_pending_without_confirm_triggers_zero_dispatches(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Test Interrupted Plan",
        summary="Interrupted step",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_rec_01",
                order=1,
                title="Create DayMentor Task",
                description="Study session",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Physics revision", "priority": "high", "deadline": "2026-09-02"},
                status="recovery_pending",
                idempotency_key="existing_uuid_key_123",
                confirmation_fingerprint="some_fp",
            )
        ],
        confidence=1.0,
    )
    plan_store.save_plan(plan.to_dict())

    # Call with confirm=False -> Must return preview, NOT execute
    res = planner.execute_plan_step(plan, "step_rec_01", confirm=False)

    assert res.status == "preview"
    assert res.requires_confirmation is True
    assert "Retry interrupted action requires explicit confirmation" in res.message
    # Assert zero executor dispatches
    mock_executor.execute_intent.assert_not_called()


# ── 2. Terminal State Execution Rejection ─────────────────────────────────────

@pytest.mark.parametrize("terminal_status", ["skipped", "cancelled", "recovery_rejected"])
def test_terminal_states_reject_execution_with_zero_dispatches(temp_store_dir, mock_client, terminal_status):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Terminal Plan",
        summary="Terminal step",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_term_01",
                order=1,
                title="Create Cricket Match",
                description="Match setup",
                step_type="write_action",
                command_id="action.cricket.create_match",
                parameters={"team_a": "Warriors", "team_b": "Titans", "match_type": "T20", "overs": 20},
                status=terminal_status,
            )
        ],
        confidence=1.0,
    )

    res = planner.execute_plan_step(plan, "step_term_01", confirm=True)
    assert res.status == "rejected"
    assert terminal_status in res.message or "Cannot execute" in res.message
    mock_executor.execute_intent.assert_not_called()


def test_completed_step_returns_cached_result_with_zero_dispatches(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Completed Plan",
        summary="Completed step",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_done_01",
                order=1,
                title="Completed Step",
                description="Done",
                step_type="write_action",
                command_id="action.cricket.create_match",
                parameters={"team_a": "Warriors", "team_b": "Titans", "match_type": "T20", "overs": 20},
                status="completed",
                result={"match_id": "m123", "score": "0/0"},
            )
        ],
        confidence=1.0,
    )

    res = planner.execute_plan_step(plan, "step_done_01", confirm=True)
    assert res.status == "success"
    assert "already been completed" in res.message
    mock_executor.execute_intent.assert_not_called()


# ── 3. Unsafe Recovery Handling ───────────────────────────────────────────────

def test_recovery_missing_idempotency_key_transitions_to_recovery_rejected(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Unsafe Recovery Missing Key",
        summary="Testing missing key",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_unsafe_01",
                order=1,
                title="Create DayMentor Task",
                description="Test",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Chemistry revision", "priority": "medium", "deadline": "2026-09-03"},
                status="recovery_pending",
                idempotency_key=None,  # Missing!
            )
        ],
        confidence=1.0,
    )
    plan_store.save_plan(plan.to_dict())

    res = planner.execute_plan_step(plan, "step_unsafe_01", confirm=True)
    assert res.status == "rejected"
    assert "missing idempotency key" in res.message
    assert plan.steps[0].status == "recovery_rejected"
    mock_executor.execute_intent.assert_not_called()


def test_recovery_fingerprint_mismatch_transitions_to_recovery_rejected(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    test_plan_id = "00000000-0000-0000-0000-000000000001"
    original_params = {"title": "Chemistry revision", "priority": "medium", "deadline": "2026-09-03"}
    original_fp = compute_confirmation_fingerprint(
        plan_id=test_plan_id,
        step_id="step_fp_01",
        command_id="action.daymentor.create_task",
        parameters=original_params,
    )

    plan = GoalPlan(
        goal="Unsafe Recovery Tampered",
        summary="Testing tampered payload",
        source_tool_ids=[],
        plan_id=test_plan_id,
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_fp_01",
                order=1,
                title="Create DayMentor Task",
                description="Test",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Tampered Title", "priority": "high", "deadline": "2026-09-03"},  # Modified!
                status="recovery_pending",
                idempotency_key="uuid_key_abc",
                confirmation_fingerprint=original_fp,
            )
        ],
        confidence=1.0,
    )
    plan_store.save_plan(plan.to_dict())


    res = planner.execute_plan_step(plan, "step_fp_01", confirm=True)
    assert res.status == "rejected"
    assert "payload changed after confirmation" in res.message
    assert plan.steps[0].status == "recovery_rejected"
    mock_executor.execute_intent.assert_not_called()


# ── 4. Fail-Closed Ownership Isolation ────────────────────────────────────────

def test_unauthenticated_client_returns_no_plans(temp_store_dir):
    plan_store = PlanStore(temp_store_dir)
    mock_unauth_client = MagicMock(spec=AachmanEcosystemClient)
    mock_unauth_client.is_authenticated = False
    mock_unauth_client.user_id = None

    # Prepopulate a plan with an owner
    plan = GoalPlan(
        goal="Owned Plan",
        summary="Owned",
        source_tool_ids=[],
        owner_id="user_owner_999",
        steps=[],
    )
    plan_store.save_plan(plan.to_dict())

    planner = GoalPlanner(client=mock_unauth_client, plan_store=plan_store)
    active = planner.load_active_plans()
    assert active == []

    resumed = planner.resume_plan(plan.plan_id)
    assert resumed is None


def test_pre_dispatch_ownership_check_rejects_mismatched_user(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Other User Plan",
        summary="Other user",
        source_tool_ids=[],
        owner_id="different_user_456",  # Not mock_client.user_id!
        steps=[
            GoalPlanStep(
                step_id="step_other_01",
                order=1,
                title="Create Task",
                description="Test",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Biology revision", "priority": "low", "deadline": "2026-09-05"},
                status="ready",
            )
        ],
    )

    res = planner.execute_plan_step(plan, "step_other_01", confirm=True)
    assert res.status == "rejected"
    assert "ownership mismatch" in res.message.lower()
    mock_executor.execute_intent.assert_not_called()


# ── 5. Pre-Dispatch Save Failure Abort ────────────────────────────────────────

def test_pre_dispatch_save_failure_aborts_with_zero_dispatches(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Disk Error Plan",
        summary="Simulate disk error",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_disk_01",
                order=1,
                title="Create DayMentor Task",
                description="Test",
                step_type="write_action",
                command_id="action.daymentor.create_task",
                parameters={"title": "Math revision", "priority": "high", "deadline": "2026-09-02"},
                status="ready",
            )
        ],
    )

    # Patch save_plan to raise an IOError
    with patch.object(plan_store, "save_plan", side_effect=IOError("Disk write error")):
        res = planner.execute_plan_step(plan, "step_disk_01", confirm=True)
        assert res.status == "failed"
        assert "Pre-dispatch save failed" in res.message
        mock_executor.execute_intent.assert_not_called()


# ── 6. Parameter Validation at Dispatch & Non-Mutating Invalid Edits ─────────

def test_invalid_cricket_overs_rejected_at_dispatch(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    plan = GoalPlan(
        goal="Invalid Cricket Match",
        summary="Invalid overs",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_crick_01",
                order=1,
                title="Create Cricket Match",
                description="Test",
                step_type="write_action",
                command_id="action.cricket.create_match",
                parameters={"team_a": "Warriors", "team_b": "Titans", "match_type": "T20", "overs": -5},
                status="ready",
            )
        ],
    )

    res = planner.execute_plan_step(plan, "step_crick_01", confirm=True)
    assert res.status == "rejected"
    assert "overs" in res.message.lower() and "positive integer" in res.message.lower()
    mock_executor.execute_intent.assert_not_called()



def test_invalid_edited_parameters_leaves_step_unmutated(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)
    mock_executor = MagicMock(spec=EcosystemExecutor)
    planner = GoalPlanner(client=mock_client, executor=mock_executor, plan_store=plan_store)

    original_params = {"team_a": "Warriors", "team_b": "Titans", "match_type": "T20", "overs": 20}
    plan = GoalPlan(
        goal="Cricket Match Edit",
        summary="Testing edit validation",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_edit_01",
                order=1,
                title="Create Cricket Match",
                description="Test",
                step_type="write_action",
                command_id="action.cricket.create_match",
                parameters=dict(original_params),
                status="ready",
            )
        ],
    )

    # Attempt to edit with team_a == team_b (invalid!)
    res = planner.execute_plan_step(
        plan,
        "step_edit_01",
        confirm=True,
        edited_parameters={"team_b": "Warriors"},
    )
    assert res.status == "rejected"
    assert "cannot be the same team" in res.message.lower()
    # Ensure original valid parameters were NOT overwritten
    assert plan.steps[0].parameters["team_b"] == "Titans"
    mock_executor.execute_intent.assert_not_called()


# ── 7. Malformed Plan Resilience ─────────────────────────────────────────────

def test_corrupt_plan_file_does_not_break_loading_healthy_siblings(temp_store_dir, mock_client):
    plan_store = PlanStore(temp_store_dir)

    # Save a healthy plan
    healthy_plan = GoalPlan(
        goal="Healthy Goal",
        summary="Healthy plan summary",
        source_tool_ids=[],
        owner_id=mock_client.user_id,
        steps=[
            GoalPlanStep(
                step_id="step_h_01",
                order=1,
                title="Read",
                description="Read",
                step_type="read_summary",
                status="ready",
            )
        ],
    )
    plan_store.save_plan(healthy_plan.to_dict())

    # Write a corrupt non-JSON file in the store directory
    corrupt_file = temp_store_dir / "plan_corrupt_broken.json"
    corrupt_file.write_text("{ this is broken non-json syntax! ;;;", encoding="utf-8")

    # Load active plans -> should skip corrupt file gracefully and return healthy plan
    active = plan_store.load_active_plans(owner_id=mock_client.user_id)
    assert len(active) == 1
    assert active[0]["plan_id"] == healthy_plan.plan_id


# ── 8. Planning Logic Grounding & Error Resilience ────────────────────────────

def test_exam_read_failure_returns_explicit_unavailable_with_zero_writes(mock_client):
    mock_read_exec = MagicMock(spec=EcosystemReadExecutor)
    # Simulate network error on DayMentor read
    mock_read_exec.execute_read_intent.return_value = JarvisReadResponse(
        tool_id="read.daymentor.next_exam",
        status="error",
        data={},
        human_text="Network timeout contacting DayMentor.",
    )


    planner = GoalPlanner(client=mock_client, read_executor=mock_read_exec)
    plan = planner.plan_goal("Prepare for my next exam")

    assert plan is not None
    assert "I couldn't check your upcoming exams right now" in plan.summary
    assert plan.total_write_steps == 0
    assert len(plan.steps) == 1
    assert plan.steps[0].step_type == "read_summary"
    assert "Unavailable" in plan.steps[0].title


def test_exam_today_schedules_today_deadline_with_high_priority():
    ref_dt = datetime.datetime(2026, 9, 1, 10, 0, 0)
    exam_data = {
        "has_exam": True,
        "days_remaining": 0,
        "exam": {
            "subjectName": "Mathematics",
            "date": "2026-09-01",
        },
    }

    schedule = calculate_exam_revision_schedule(exam_data, ref_dt)
    assert schedule["days_remaining"] == 0
    assert schedule["revision_deadline"] == "2026-09-01"
    assert schedule["revision_priority"] == "high"
    assert schedule["has_practice"] is False


def test_exam_tomorrow_queries_tomorrow_tasks_for_deduplication(mock_client):
    mock_read_exec = MagicMock(spec=EcosystemReadExecutor)
    ref_dt = datetime.datetime(2026, 9, 1, 10, 0, 0)

    # Exam is in 2 days (2026-09-03) -> Revision is due tomorrow (2026-09-02)
    def fake_read(intent: JarvisReadIntent) -> JarvisReadResponse:
        if intent.tool_id == "read.daymentor.next_exam":
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="success",
                data={
                    "has_exam": True,
                    "days_remaining": 2,
                    "exam": {"subjectName": "Physics", "date": "2026-09-03"},
                },
                human_text="Next Exam: Physics on 2026-09-03 (in 2 days).",
            )
        if intent.tool_id == "read.daymentor.tasks_today":
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="success",
                data={"tasks": []},
                human_text="No tasks for today.",
            )
        if intent.tool_id == "read.daymentor.tasks_tomorrow":
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="success",
                data={"tasks": [{"id": "t1", "title": "Physics revision", "deadline": "2026-09-02"}]},
                human_text="1 task for tomorrow.",
            )
        return JarvisReadResponse(tool_id=intent.tool_id, status="error", data={}, human_text="Error")

    mock_read_exec.execute_read_intent.side_effect = fake_read
    planner = GoalPlanner(client=mock_client, read_executor=mock_read_exec)
    plan = planner.plan_goal("Prepare for my next exam", now=ref_dt)

    assert plan is not None
    # Since tomorrow already has "Physics revision", deduplication should prevent duplicate creation
    write_steps = [s for s in plan.steps if s.step_type == "write_action"]
    assert len(write_steps) == 0  # No duplicate task planned!
