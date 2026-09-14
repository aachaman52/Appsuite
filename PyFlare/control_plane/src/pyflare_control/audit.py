"""Append-only JSON Lines audit sink with recursive secret redaction."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

_SECRET_MARKERS = ("token", "secret", "password", "api_key", "authorization")


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if any(marker in normalized_key.lower() for marker in _SECRET_MARKERS):
                output[normalized_key] = "[REDACTED]"
            else:
                output[normalized_key] = _json_safe(item)
        return output
    if isinstance(value, (set, frozenset, tuple, list)):
        return [_json_safe(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    event_type: str
    task_id: str
    actor: str
    payload: Mapping[str, Any]
    occurred_at: str


class JsonlAuditSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(
            _json_safe(event),
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(serialized + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def new_event(
    *,
    event_id: str,
    event_type: str,
    task_id: str,
    actor: str,
    payload: Mapping[str, Any],
) -> AuditEvent:
    return AuditEvent(
        event_id=event_id,
        event_type=event_type,
        task_id=task_id,
        actor=actor,
        payload=payload,
        occurred_at=datetime.now(UTC).isoformat(),
    )
