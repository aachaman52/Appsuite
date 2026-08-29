"""Integration Tests for Jarvis Plan Resume & Restart Recovery v1."""
from __future__ import annotations

import datetime
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
    AachmanEcosystemClient,
    GoalPlanner,
    GoalPlan,
    GoalPlanStep,
    PlanStore,
    EcosystemReadExecutor,
    JarvisReadResponse,
    ExecutionResult,
)


class MockResumeReadExecutor(EcosystemReadExecutor):
    """Mock read executor simulating live ecosystem states."""

    def __init__(self, exam_data=None):
        super().__init__(client=AachmanEcosystemClient(session_file=Path("/tmp/mock_session.json")))
        self.client._in_memory_access_token = "dummy_token"
        self.client.metadata = {"user_id": "test_uid", "email": "tester@aachman.org"}
        self.exam_data = exam_data

    def execute_read_intent(self, intent):
        if intent.tool_id == "read.daymentor.next_exam":
            if self.exam_data:
                return JarvisReadResponse(
                    tool_id="read.daymentor.next_exam",
                    status="success",
                    human_text=f"Exam scheduled: {self.exam_data['subjectName']}",
                    data={"has_exam": True, "exam": self.exam_data, "days_remaining": self.exam_data["days_remaining"]},
                )
            return JarvisReadResponse(
                tool_id="read.daymentor.next_exam",
                status="empty",
                human_text="No exams.",
                data={"has_exam": False},
            )
        elif intent.tool_id in ("read.daymentor.tasks_today", "read.daymentor.tasks_tomorrow"):
            return JarvisReadResponse(tool_id=intent.tool_id, status="empty", human_text="No tasks", data={"tasks": []})
        return super().execute_read_intent(intent)


class MockResumeExecutor:
    """Mock executor tracking calls and verifying idempotency keys."""

    def __init__(self):
        self.executed_calls = []

    def execute_intent(self, intent, confirm=False):
        if not confirm:
            return ExecutionResult(command_id=intent.command_id, status="preview", message="Preview")
        self.executed_calls.append(intent)
        return ExecutionResult(
            command_id=intent.command_id,
            status="success",
            message=f"Executed {intent.summary}",
            deep_link=f"https://app.aachman.org/{intent.command_id}",
            preview_data={"entity_id": f"task_{intent.idempotency_key[:8]}"},
        )


def test_restart_after_partial_completion():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        exam = {"subjectName": "Mathematics", "date": "2026-09-04", "days_remaining": 5}
        reads = MockResumeReadExecutor(exam_data=exam)
        mock_exec1 = MockResumeExecutor()

        # Session 1: Create plan and execute Step 1 (read) and Step 2 (write)
        planner1 = GoalPlanner(read_executor=reads, executor=mock_exec1, plan_store=store)
        plan = planner1.plan_goal("prepare me for my next exam")
        assert plan is not None
        plan_id = plan.plan_id

        # Step 2 is write action
        write_step = [s for s in plan.steps if s.step_type == "write_action"][0]
        res = planner1.execute_plan_step(plan, write_step.step_id, confirm=True)
        assert res.status == "success"
        key_step1 = write_step.idempotency_key

        # Destroy Session 1 (simulating application shutdown)
        del planner1
        del mock_exec1

        # Session 2: Reopen application, load active plans
        mock_exec2 = MockResumeExecutor()
        planner2 = GoalPlanner(read_executor=reads, executor=mock_exec2, plan_store=store)
        active_plans = planner2.load_active_plans()

        assert len(active_plans) == 1
        resumed_plan = active_plans[0]
        assert resumed_plan.plan_id == plan_id

        # Verify completed steps are preserved and immutable
        step2_resumed = [s for s in resumed_plan.steps if s.step_id == write_step.step_id][0]
        assert step2_resumed.status == "completed"
        assert step2_resumed.idempotency_key == key_step1

        # Execute next pending step in Session 2
        next_step = [s for s in resumed_plan.steps if s.status in ("ready", "planned") and s.step_type == "write_action"][0]
        res_next = planner2.execute_plan_step(resumed_plan, next_step.step_id, confirm=True)
        assert res_next.status == "success"
        assert next_step.status == "completed"
        assert next_step.idempotency_key != key_step1

        print("✓ Restart after partial completion test passed: Preserved state across restarts")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_response_loss_restart_recovery():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        exam = {"subjectName": "Physics", "date": "2026-09-04", "days_remaining": 5}
        reads = MockResumeReadExecutor(exam_data=exam)
        mock_exec = MockResumeExecutor()

        planner = GoalPlanner(read_executor=reads, executor=mock_exec, plan_store=store)
        plan = planner.plan_goal("prepare me for my next exam")
        write_step = [s for s in plan.steps if s.step_type == "write_action"][0]

        # Simulate crash while step is executing with key X
        write_step.idempotency_key = "crash_key_12345"
        write_step.status = "executing"
        store.save_plan(plan.to_dict())

        # Simulate restart
        del planner
        store2 = PlanStore(storage_dir=temp_dir)
        planner2 = GoalPlanner(read_executor=reads, executor=mock_exec, plan_store=store2)

        resumed_plan = planner2.resume_plan(plan.plan_id)
        assert resumed_plan is not None

        resumed_step = [s for s in resumed_plan.steps if s.step_id == write_step.step_id][0]
        # Status recovered to recovery_pending
        assert resumed_step.status == "recovery_pending"
        assert resumed_step.idempotency_key == "crash_key_12345"

        # Retry step using the resumed plan
        res_retry = planner2.execute_plan_step(resumed_plan, resumed_step.step_id, confirm=True)
        assert res_retry.status == "success"
        # Verify identical key was used
        assert mock_exec.executed_calls[-1].idempotency_key == "crash_key_12345"
        print("✓ Response-loss restart recovery test passed: Reused identical idempotency key")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_skipped_and_cancelled_immutability_on_resume():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        exam = {"subjectName": "Chemistry", "date": "2026-09-04", "days_remaining": 5}
        reads = MockResumeReadExecutor(exam_data=exam)
        mock_exec = MockResumeExecutor()

        planner = GoalPlanner(read_executor=reads, executor=mock_exec, plan_store=store)
        plan = planner.plan_goal("prepare me for my next exam")
        write_steps = [s for s in plan.steps if s.step_type == "write_action"]

        # Skip step 1, cancel plan
        planner.skip_plan_step(plan, write_steps[0].step_id)
        planner.cancel_plan(plan)

        # Reopen on restart
        del planner
        planner2 = GoalPlanner(read_executor=reads, executor=mock_exec, plan_store=store)
        resumed = planner2.resume_plan(plan.plan_id)

        assert resumed.steps[1].status in ("skipped", "cancelled")
        # Skipped/cancelled steps must not appear in active plans
        assert len(planner2.load_active_plans()) == 0
        print("✓ Skipped and cancelled immutability test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_user_switch_isolation():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        reads = MockResumeReadExecutor()

        # Alice creates plan
        client_alice = AachmanEcosystemClient(session_file=Path("/tmp/alice.json"))
        client_alice.metadata = {"user_id": "alice_uid", "email": "alice@aachman.org"}
        client_alice._in_memory_access_token = "alice_token"

        planner_alice = GoalPlanner(client=client_alice, read_executor=reads, plan_store=store)
        plan = planner_alice.plan_goal("prepare me for my next exam")
        assert plan is not None

        # Bob logs in
        client_bob = AachmanEcosystemClient(session_file=Path("/tmp/bob.json"))
        client_bob.metadata = {"user_id": "bob_uid", "email": "bob@aachman.org"}
        client_bob._in_memory_access_token = "bob_token"

        planner_bob = GoalPlanner(client=client_bob, read_executor=reads, plan_store=store)
        # Bob cannot load Alice's active plans
        assert len(planner_bob.load_active_plans()) == 0
        # Bob cannot resume Alice's plan by ID
        assert planner_bob.resume_plan(plan.plan_id) is None
        print("✓ User switch isolation test passed: Cross-user plan access blocked")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_zero_write_side_effects_on_load():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        store = PlanStore(storage_dir=temp_dir)
        reads = MockResumeReadExecutor()
        mock_exec = MockResumeExecutor()

        planner = GoalPlanner(read_executor=reads, executor=mock_exec, plan_store=store)
        plan = planner.plan_goal("prepare me for my next exam")

        # Loading or resuming without confirming a write step produces ZERO calls to executor
        calls_before = len(mock_exec.executed_calls)
        planner.load_active_plans()
        planner.resume_plan(plan.plan_id)
        assert len(mock_exec.executed_calls) == calls_before == 0
        print("✓ Zero write side-effects on load test passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("\n=== RUNNING PLAN RESUME INTEGRATION TESTS ===")
    test_restart_after_partial_completion()
    test_response_loss_restart_recovery()
    test_skipped_and_cancelled_immutability_on_resume()
    test_user_switch_isolation()
    test_zero_write_side_effects_on_load()
    print("\n=== ALL PLAN RESUME INTEGRATION TESTS PASSED ===\n")
