"""World Model storage and job-local runtime knowledge base."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..db import Database


class WorldModel:
    """In-memory world state for a single job with SQLite persistence."""

    def __init__(self, job_id: str, db: Optional[Database] = None):
        self.job_id = job_id
        self.db = db
        self._state: Dict[str, Any] = {}
        if self.db:
            try:
                self._create_table_if_missing()
                self._load_from_db()
            except Exception:
                pass

    def _create_table_if_missing(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS world_model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT,
                updated_at REAL NOT NULL,
                UNIQUE(job_id, key)
            );
            """
        )

    def _load_from_db(self) -> None:
        if not self.db:
            return
        rows = self.db.get_world_model_entries(self.job_id)
        for row in rows:
            if row.get("key"):
                self._state[row["key"]] = row.get("value")

    def update(self, key: str, value: Any) -> None:
        self._state[key] = value
        if self.db:
            try:
                self.db.add_world_model_entry(self.job_id, key, value)
            except Exception:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._state)

    def keys(self) -> list[str]:
        return list(self._state.keys())

    def items(self) -> list[tuple[str, Any]]:
        return list(self._state.items())
