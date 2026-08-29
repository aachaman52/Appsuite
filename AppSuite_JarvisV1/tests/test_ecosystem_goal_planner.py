"""Unit and Integration Tests for Jarvis Multi-Step Goal Planner v1."""
from __future__ import annotations

import datetime
from pathlib import Path
import sys

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
    EcosystemReadExecutor,
    JarvisReadResponse,
    ExecutionResult,
)


class MockGoalReadExecutor(EcosystemReadExecutor):
    """Mock read executor simulating live ecosystem states for goal planning."""

    def __init__(self, exam_data=None, tasks_data=None, match_data=None, hackathon_data=None):
        super().__init__(client=AachmanEcosystemClient(session_file=Path("/tmp/mock_session.json")))
        self.client._in_memory_access_token = "dummy_token"
        self.client.metadata = {"user_id": "test_uid", "email": "tester@aachman.org"}
        self.exam_data = exam_data
        self.tasks_data = tasks_data or []
        self.match_data = match_data
        self.hackathon_data = hackathon_data

    def execute_read_intent(self, intent):
        if intent.tool_id == "read.daymentor.next_exam":
            if self.exam_data:
                return JarvisReadResponse(
                    tool_id="read.daymentor.next_exam",
                    status="success",
                    human_text=f"Your next scheduled exam is {self.exam_data['subjectName']} on {self.exam_data['date']} (in {self.exam_data['days_remaining']} days).",
                    data={"has_exam": True, "exam": self.exam_data, "days_remaining": self.exam_data["days_remaining"]},
                )
            return JarvisReadResponse(
                tool_id="read.daymentor.next_exam",
                status="empty",
                human_text="You don't have any upcoming exams scheduled.",
                data={"has_exam": False},
            )

        elif intent.tool_id in ("read.daymentor.tasks_today", "read.daymentor.tasks_tomorrow"):
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="success" if self.tasks_data else "empty",
                human_text="Tasks list",
                data={"tasks": self.tasks_data, "count": len(self.tasks_data)},
            )

        elif intent.tool_id == "read.cricket.last_match":
            if self.match_data:
                return JarvisReadResponse(
                    tool_id="read.cricket.last_match",
                    status="success",
                    human_text=f"Last cricket match: {self.match_data['team_a']} vs {self.match_data['team_b']}",
                    data={"has_match": True, "match": self.match_data},
                )
            return JarvisReadResponse(
                tool_id="read.cricket.last_match",
                status="empty",
                human_text="No matches found.",
                data={"has_match": False},
            )

        elif intent.tool_id == "read.hackathon.latest_result":
            if self.hackathon_data:
                return JarvisReadResponse(
                    tool_id="read.hackathon.latest_result",
                    status="success",
                    human_text=f"Completed {self.hackathon_data['title']} score {self.hackathon_data['score']}/100",
                    data={"has_result": True, "result": self.hackathon_data},
                )
            return JarvisReadResponse(
                tool_id="read.hackathon.latest_result",
                status="empty",
                human_text="No hackathon results.",
                data={"has_result": False},
            )

        return super().execute_read_intent(intent)


class MockGoalExecutor:
    """Mock action executor tracking executed calls and idempotency keys."""

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
        )


def test_exam_preparation_multi_step_plan():
    exam = {"subjectName": "Mathematics", "date": "2026-09-04", "days_remaining": 5}
    reads = MockGoalReadExecutor(exam_data=exam, tasks_data=[])
    planner = GoalPlanner(read_executor=reads)

    now = datetime.datetime(2026, 8, 30)
    plan = planner.plan_goal("prepare me for my next exam", now=now)

    assert plan is not None
    assert "Mathematics" in plan.goal
    assert len(plan.steps) >= 2
    assert plan.steps[0].step_type == "read_summary"
    assert plan.steps[0].status == "completed"

    write_steps = [s for s in plan.steps if s.step_type == "write_action"]
    assert len(write_steps) == 2  # Revision + Practice Problem Set
    assert write_steps[0].command_id == "action.daymentor.create_task"
    assert "Mathematics revision" in write_steps[0].parameters["title"]
    assert write_steps[1].command_id == "action.daymentor.create_task"
    assert "practice" in write_steps[1].parameters["title"].lower()
    print("✓ Exam preparation multi-step plan test passed: Generated sequenced roadmap")


def test_exam_plan_duplicate_handling():
    exam = {"subjectName": "Mathematics", "date": "2026-09-04", "days_remaining": 5}
    existing = [{"title": "Mathematics revision", "priority": "high", "deadline": "2026-08-30"}]
    reads = MockGoalReadExecutor(exam_data=exam, tasks_data=existing)
    planner = GoalPlanner(read_executor=reads)

    plan = planner.plan_goal("prepare me for my next exam")
    assert plan is not None
    # Revision step should be omitted because it already exists
    write_titles = [s.title for s in plan.steps if s.step_type == "write_action"]
    assert not any("Revision" in t for t in write_titles)
    print("✓ Duplicate handling test passed: Skipped existing revision task in multi-step plan")


def test_step_by_step_execution_and_idempotency():
    exam = {"subjectName": "Physics", "date": "2026-09-03", "days_remaining": 4}
    reads = MockGoalReadExecutor(exam_data=exam, tasks_data=[])
    mock_exec = MockGoalExecutor()
    planner = GoalPlanner(read_executor=reads, executor=mock_exec)

    plan = planner.plan_goal("prepare me for my next exam")
    assert plan is not None

    write_steps = [s for s in plan.steps if s.step_type == "write_action"]
    assert len(write_steps) >= 1
    step1 = write_steps[0]

    # Execute Step 1
    res1 = planner.execute_plan_step(plan, step1.step_id, confirm=True)
    assert res1.status == "success"
    assert step1.status == "completed"
    assert step1.idempotency_key is not None
    key1 = step1.idempotency_key

    # Re-executing completed Step 1 is idempotent and does not dispatch new write
    init_call_count = len(mock_exec.executed_calls)
    res1_repeat = planner.execute_plan_step(plan, step1.step_id, confirm=True)
    assert res1_repeat.status == "success"
    assert len(mock_exec.executed_calls) == init_call_count

    if len(write_steps) >= 2:
        step2 = write_steps[1]
        res2 = planner.execute_plan_step(plan, step2.step_id, confirm=True)
        assert res2.status == "success"
        assert step2.status == "completed"
        assert step2.idempotency_key is not None
        assert step2.idempotency_key != key1, "Different steps must have distinct idempotency keys!"

    print("✓ Step-by-step execution & idempotency test passed: Distinct per-step keys verified")


def test_skip_and_cancel_flow():
    exam = {"subjectName": "Chemistry", "date": "2026-09-05", "days_remaining": 6}
    reads = MockGoalReadExecutor(exam_data=exam, tasks_data=[])
    mock_exec = MockGoalExecutor()
    planner = GoalPlanner(read_executor=reads, executor=mock_exec)

    plan = planner.plan_goal("prepare me for my next exam")
    write_steps = [s for s in plan.steps if s.step_type == "write_action"]

    # Confirm step 1
    planner.execute_plan_step(plan, write_steps[0].step_id, confirm=True)
    assert write_steps[0].status == "completed"

    if len(write_steps) > 1:
        # Skip step 2
        planner.skip_plan_step(plan, write_steps[1].step_id)
        assert write_steps[1].status == "skipped"

    # Cancel plan
    planner.cancel_plan(plan)
    for s in plan.steps:
        assert s.status in ("completed", "skipped", "cancelled")

    # Only 1 mutation was executed
    assert len(mock_exec.executed_calls) == 1
    print("✓ Skip & cancel test passed: Only confirmed steps executed")


def test_cricket_and_hackathon_goal_plans():
    # Cricket Rematch Plan
    match = {"team_a": "India", "team_b": "Australia", "match_type": "T20"}
    reads = MockGoalReadExecutor(match_data=match)
    planner = GoalPlanner(read_executor=reads)

    cricket_plan = planner.plan_goal("create a rematch plan")
    assert cricket_plan is not None
    assert any(s.command_id == "action.cricket.create_match" for s in cricket_plan.steps)

    # Hackathon Practice Plan
    hack = {"title": "LearnFlow AI", "score": 92, "difficulty": "medium"}
    reads_hack = MockGoalReadExecutor(hackathon_data=hack)
    planner_hack = GoalPlanner(read_executor=reads_hack)

    hack_plan = planner_hack.plan_goal("help me practice for another hackathon")
    assert hack_plan is not None
    hack_write = next(s for s in hack_plan.steps if s.step_type == "write_action")
    assert hack_write.parameters["difficulty"] == "hard"  # Progressed to hard
    print("✓ Cricket & Hackathon goal plans test passed: Correctly structured domain steps")


def test_unauthenticated_goal_planning():
    unauth_client = AachmanEcosystemClient(session_file=Path("/tmp/nonexistent.json"))
    planner = GoalPlanner(client=unauth_client)

    plan = planner.plan_goal("prepare me for my next exam")
    assert plan is not None
    assert len(plan.steps) == 0
    assert "Sign in" in plan.summary
    print("✓ Unauthenticated goal plan test passed: Prompts sign in cleanly")


def test_zero_plan_generation_side_effects():
    exam = {"subjectName": "History", "date": "2026-09-02", "days_remaining": 3}
    reads = MockGoalReadExecutor(exam_data=exam, tasks_data=[])
    mock_exec = MockGoalExecutor()
    planner = GoalPlanner(read_executor=reads, executor=mock_exec)

    plan = planner.plan_goal("prepare me for my next exam")
    assert plan is not None
    # Generating the plan MUST NOT execute any writes
    assert len(mock_exec.executed_calls) == 0
    print("✓ Zero side-effects test passed: Plan generation produced 0 writes")


if __name__ == "__main__":
    print("\n=== RUNNING JARVIS MULTI-STEP GOAL PLANNER TESTS ===")
    test_exam_preparation_multi_step_plan()
    test_exam_plan_duplicate_handling()
    test_step_by_step_execution_and_idempotency()
    test_skip_and_cancel_flow()
    test_cricket_and_hackathon_goal_plans()
    test_unauthenticated_goal_planning()
    test_zero_plan_generation_side_effects()
    print("\n=== ALL JARVIS MULTI-STEP GOAL PLANNER TESTS PASSED 100% ===\n")
