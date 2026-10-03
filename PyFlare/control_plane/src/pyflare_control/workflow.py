"""Deterministic PyFlare task state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class TaskStatus(StrEnum):
    DRAFT = "draft"
    AUTHORIZED = "authorized"
    QUEUED = "queued"
    RUNNING = "running"
    VALIDATING = "validating"
    RETRYING = "retrying"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    MERGED = "merged"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {TaskStatus.MERGED, TaskStatus.FAILED, TaskStatus.CANCELLED}
)

_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.AUTHORIZED, TaskStatus.CANCELLED}),
    TaskStatus.AUTHORIZED: frozenset({TaskStatus.QUEUED, TaskStatus.CANCELLED}),
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.VALIDATING,
            TaskStatus.RETRYING,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.VALIDATING: frozenset(
        {
            TaskStatus.COMPLETED,
            TaskStatus.RETRYING,
            TaskStatus.REVIEW_REQUIRED,
            TaskStatus.FAILED,
        }
    ),
    TaskStatus.RETRYING: frozenset(
        {
            TaskStatus.QUEUED,
            TaskStatus.REVIEW_REQUIRED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.REVIEW_REQUIRED: frozenset(
        {TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.COMPLETED: frozenset({TaskStatus.MERGED}),
    TaskStatus.MERGED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


class InvalidTransitionError(ValueError):
    def __init__(self, current: TaskStatus, target: TaskStatus) -> None:
        super().__init__(f"invalid task transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


def require_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    project_id: str
    status: TaskStatus
    revision: int
    created_at: str
    updated_at: str
    task_spec: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaskEvent:
    sequence: int
    event_id: str
    task_id: str
    event_type: str
    previous_status: TaskStatus | None
    new_status: TaskStatus
    reason: str
    actor: str
    occurred_at: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    capability_id: str
    depends_on: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    task_id: str
    steps: tuple[WorkflowStep, ...]

    def __post_init__(self) -> None:
        step_ids = {step.step_id for step in self.steps}
        if len(step_ids) != len(self.steps):
            raise ValueError("workflow step IDs must be unique")
        for step in self.steps:
            unknown = step.depends_on - step_ids
            if unknown:
                raise ValueError(
                    f"step {step.step_id} has unknown dependencies: {sorted(unknown)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id} cannot depend on itself")
        self._require_acyclic()

    def _require_acyclic(self) -> None:
        dependencies = {
            step.step_id: set(step.depends_on)
            for step in self.steps
        }
        ready = [step_id for step_id, deps in dependencies.items() if not deps]
        visited: set[str] = set()
        while ready:
            step_id = ready.pop()
            if step_id in visited:
                continue
            visited.add(step_id)
            for candidate, deps in dependencies.items():
                if step_id in deps:
                    deps.remove(step_id)
                    if not deps:
                        ready.append(candidate)
        if len(visited) != len(dependencies):
            raise ValueError("workflow plan contains a dependency cycle")

    def ready_steps(self, completed: frozenset[str]) -> tuple[WorkflowStep, ...]:
        return tuple(
            step
            for step in self.steps
            if step.step_id not in completed and step.depends_on.issubset(completed)
        )


EMPTY_DETAILS = MappingProxyType({})
