"""Durable SQLite task journal with optimistic concurrency and idempotency."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codec import TaskSpecCodec
from .models import TaskSpec
from .workflow import TaskEvent, TaskRecord, TaskStatus, require_transition


class JournalConflictError(RuntimeError):
    pass


class TaskNotFoundError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    idempotency_key: str
    task_id: str
    operation: str
    status: str
    response: dict[str, Any] | None
    created_at: str
    updated_at: str
    is_new: bool = False


class TaskJournal:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    task_spec_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS task_events_task_sequence
                    ON task_events(task_id, sequence);

                CREATE TABLE IF NOT EXISTS idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );
                """
            )

    def create_task(
        self,
        task: TaskSpec,
        *,
        actor: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> TaskRecord:
        now = self._now()
        task_json = self._encode(TaskSpecCodec.dump(task))
        metadata_json = self._encode(dict(metadata or {}))
        event_id = uuid.uuid4().hex
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO tasks (
                        task_id, project_id, status, revision, task_spec_json,
                        metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.project_id,
                        TaskStatus.DRAFT.value,
                        task_json,
                        metadata_json,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO task_events (
                        event_id, task_id, event_type, previous_status, new_status,
                        reason, actor, details_json, occurred_at
                    ) VALUES (?, ?, 'task_created', NULL, ?, ?, ?, '{}', ?)
                    """,
                    (
                        event_id,
                        task.task_id,
                        TaskStatus.DRAFT.value,
                        "task accepted into journal",
                        actor,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise JournalConflictError(f"task already exists: {task.task_id}") from error
        return self.require_task(task.task_id)

    def require_task(self, task_id: str) -> TaskRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise TaskNotFoundError(task_id)
        return self._task_from_row(row)

    def transition(
        self,
        task_id: str,
        target: TaskStatus,
        *,
        expected_revision: int,
        actor: str,
        reason: str,
        details: Mapping[str, Any] | None = None,
    ) -> TaskRecord:
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            current = TaskStatus(row["status"])
            revision = int(row["revision"])
            if revision != expected_revision:
                raise JournalConflictError(
                    f"revision conflict for {task_id}: expected "
                    f"{expected_revision}, found {revision}"
                )
            require_transition(current, target)
            cursor = connection.execute(
                """
                UPDATE tasks
                SET status = ?, revision = revision + 1, updated_at = ?
                WHERE task_id = ? AND revision = ?
                """,
                (target.value, now, task_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise JournalConflictError(f"concurrent update for task {task_id}")
            connection.execute(
                """
                INSERT INTO task_events (
                    event_id, task_id, event_type, previous_status, new_status,
                    reason, actor, details_json, occurred_at
                ) VALUES (?, ?, 'status_changed', ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    task_id,
                    current.value,
                    target.value,
                    reason,
                    actor,
                    self._encode(dict(details or {})),
                    now,
                ),
            )
        return self.require_task(task_id)

    def events(self, task_id: str) -> tuple[TaskEvent, ...]:
        self.require_task(task_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY sequence",
                (task_id,),
            ).fetchall()
        return tuple(self._event_from_row(row) for row in rows)

    def reserve_operation(
        self,
        *,
        idempotency_key: str,
        task_id: str,
        operation: str,
    ) -> IdempotencyRecord:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        self.require_task(task_id)
        now = self._now()
        is_new = False
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO idempotency (
                        idempotency_key, task_id, operation, status,
                        response_json, created_at, updated_at
                    ) VALUES (?, ?, ?, 'reserved', NULL, ?, ?)
                    """,
                    (idempotency_key, task_id, operation, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM idempotency WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                is_new = True
            elif row["task_id"] != task_id or row["operation"] != operation:
                raise JournalConflictError(
                    "idempotency key is already bound to another operation"
                )
        assert row is not None
        return self._idempotency_from_row(row, is_new=is_new)

    def complete_operation(
        self,
        *,
        idempotency_key: str,
        response: Mapping[str, Any],
    ) -> IdempotencyRecord:
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE idempotency
                SET status = 'completed', response_json = ?, updated_at = ?
                WHERE idempotency_key = ? AND status = 'reserved'
                """,
                (self._encode(dict(response)), now, idempotency_key),
            )
            if cursor.rowcount != 1:
                raise JournalConflictError(
                    "operation is missing, already completed or not reservable"
                )
            row = connection.execute(
                "SELECT * FROM idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        assert row is not None
        return self._idempotency_from_row(row)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _decode(value: str | None) -> Any:
        return None if value is None else json.loads(value)

    @classmethod
    def _task_from_row(cls, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            project_id=row["project_id"],
            status=TaskStatus(row["status"]),
            revision=int(row["revision"]),
            task_spec=cls._decode(row["task_spec_json"]),
            metadata=cls._decode(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _event_from_row(cls, row: sqlite3.Row) -> TaskEvent:
        previous = row["previous_status"]
        return TaskEvent(
            sequence=int(row["sequence"]),
            event_id=row["event_id"],
            task_id=row["task_id"],
            event_type=row["event_type"],
            previous_status=TaskStatus(previous) if previous else None,
            new_status=TaskStatus(row["new_status"]),
            reason=row["reason"],
            actor=row["actor"],
            details=cls._decode(row["details_json"]),
            occurred_at=row["occurred_at"],
        )

    @classmethod
    def _idempotency_from_row(
        cls,
        row: sqlite3.Row,
        *,
        is_new: bool = False,
    ) -> IdempotencyRecord:
        return IdempotencyRecord(
            idempotency_key=row["idempotency_key"],
            task_id=row["task_id"],
            operation=row["operation"],
            status=row["status"],
            response=cls._decode(row["response_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_new=is_new,
        )
