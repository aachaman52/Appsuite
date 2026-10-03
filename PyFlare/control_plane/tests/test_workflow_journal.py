from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyflare_control.journal import JournalConflictError, TaskJournal
from pyflare_control.models import Permission, ResourceBudget, TaskSpec
from pyflare_control.workflow import (
    InvalidTransitionError,
    TaskStatus,
    WorkflowPlan,
    WorkflowStep,
)


def make_task() -> TaskSpec:
    return TaskSpec(
        task_id="task-1",
        project_id="project-1",
        domain="game_development",
        operation="inspect_editor",
        required_capabilities=frozenset({"unity.editor.inspect"}),
        permissions=frozenset({Permission.READ, Permission.EXECUTE}),
        resource_budget=ResourceBudget(512, 0, 25, 0),
    )


class WorkflowJournalTests(unittest.TestCase):
    def test_durable_transitions_and_events(self) -> None:
        with TemporaryDirectory() as directory:
            journal = TaskJournal(Path(directory) / "journal.sqlite3")
            journal.initialize()
            created = journal.create_task(make_task(), actor="user:aachman")
            self.assertEqual(created.status, TaskStatus.DRAFT)
            authorized = journal.transition(
                created.task_id,
                TaskStatus.AUTHORIZED,
                expected_revision=0,
                actor="authorization-service",
                reason="grant accepted",
            )
            queued = journal.transition(
                created.task_id,
                TaskStatus.QUEUED,
                expected_revision=authorized.revision,
                actor="workflow-engine",
                reason="route ready",
            )
            self.assertEqual(queued.revision, 2)
            self.assertEqual(len(journal.events(created.task_id)), 3)

    def test_stale_revision_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            journal = TaskJournal(Path(directory) / "journal.sqlite3")
            journal.initialize()
            journal.create_task(make_task(), actor="user")
            journal.transition(
                "task-1",
                TaskStatus.AUTHORIZED,
                expected_revision=0,
                actor="policy",
                reason="allowed",
            )
            with self.assertRaises(JournalConflictError):
                journal.transition(
                    "task-1",
                    TaskStatus.QUEUED,
                    expected_revision=0,
                    actor="engine",
                    reason="stale",
                )

    def test_invalid_transition_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            journal = TaskJournal(Path(directory) / "journal.sqlite3")
            journal.initialize()
            journal.create_task(make_task(), actor="user")
            with self.assertRaises(InvalidTransitionError):
                journal.transition(
                    "task-1",
                    TaskStatus.RUNNING,
                    expected_revision=0,
                    actor="engine",
                    reason="skipped authorization",
                )

    def test_idempotency_reservation_replays_completed_result(self) -> None:
        with TemporaryDirectory() as directory:
            journal = TaskJournal(Path(directory) / "journal.sqlite3")
            journal.initialize()
            journal.create_task(make_task(), actor="user")
            first = journal.reserve_operation(
                idempotency_key="task-1:step-1:attempt-1",
                task_id="task-1",
                operation="unity.editor.inspect",
            )
            self.assertTrue(first.is_new)
            journal.complete_operation(
                idempotency_key=first.idempotency_key,
                response={"status": "succeeded"},
            )
            replay = journal.reserve_operation(
                idempotency_key=first.idempotency_key,
                task_id="task-1",
                operation="unity.editor.inspect",
            )
            self.assertFalse(replay.is_new)
            self.assertEqual(replay.response, {"status": "succeeded"})

    def test_workflow_rejects_cycles_and_reports_ready_steps(self) -> None:
        plan = WorkflowPlan(
            task_id="task",
            steps=(
                WorkflowStep("inspect", "unity.editor.inspect"),
                WorkflowStep(
                    "create",
                    "unity.game_object.create",
                    frozenset({"inspect"}),
                ),
            ),
        )
        self.assertEqual(
            tuple(step.step_id for step in plan.ready_steps(frozenset())),
            ("inspect",),
        )
        with self.assertRaises(ValueError):
            WorkflowPlan(
                task_id="bad",
                steps=(
                    WorkflowStep("a", "a", frozenset({"b"})),
                    WorkflowStep("b", "b", frozenset({"a"})),
                ),
            )


if __name__ == "__main__":
    unittest.main()
