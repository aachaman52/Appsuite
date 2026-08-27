"""Persistent historical performance storage and Bayesian smoothing for PyFlare Router."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pyflare.router.models import HardwareTier, RouteOutcome, TaskType


class RouterHistoryTracker:
    """Tracks and calculates smoothed historical metrics for route candidates."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or "./data/pyflare.db"
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS router_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    validation_score REAL DEFAULT 1.0,
                    hardware_tier TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_router_history_candidate ON router_history(candidate_id, task_type)")
            conn.commit()

    def record_outcome(self, outcome: RouteOutcome) -> None:
        """Store execution outcome of a route candidate."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO router_history (
                    task_id, candidate_id, task_type, success, duration_seconds,
                    cost_usd, error_message, retry_count, validation_score,
                    hardware_tier, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.task_id,
                outcome.candidate_id,
                str(outcome.task_type.value if hasattr(outcome.task_type, "value") else outcome.task_type),
                1 if outcome.success else 0,
                outcome.duration_seconds,
                outcome.cost_usd,
                outcome.error_message,
                outcome.retry_count,
                outcome.validation_score,
                str(outcome.hardware_tier.value if hasattr(outcome.hardware_tier, "value") else outcome.hardware_tier),
                outcome.timestamp or time.time(),
            ))
            conn.commit()

    def get_candidate_stats(self, candidate_id: str, task_type: Optional[TaskType] = None) -> Dict[str, Any]:
        """
        Compute smoothed historical performance metrics for candidate.
        Uses Bayesian smoothing (m-estimate) to prevent single outlier runs
        from destabilizing routing scores.
        """
        with self._get_connection() as conn:
            if task_type:
                t_val = task_type.value if hasattr(task_type, "value") else str(task_type)
                cursor = conn.execute(
                    "SELECT success, duration_seconds, cost_usd FROM router_history WHERE candidate_id = ? AND task_type = ?",
                    (candidate_id, t_val),
                )
            else:
                cursor = conn.execute(
                    "SELECT success, duration_seconds, cost_usd FROM router_history WHERE candidate_id = ?",
                    (candidate_id,),
                )
            rows = cursor.fetchall()

        sample_count = len(rows)
        if sample_count == 0:
            # Default uncalibrated score
            return {
                "sample_count": 0,
                "raw_success_rate": 1.0,
                "smoothed_success_rate": 0.85,  # Prior belief
                "avg_duration": 1.0,
                "avg_cost": 0.0,
                "has_sufficient_samples": False,
            }

        successes = sum(1 for r in rows if r["success"] == 1)
        raw_success_rate = successes / sample_count
        avg_duration = sum(r["duration_seconds"] for r in rows) / sample_count
        avg_cost = sum(r["cost_usd"] for r in rows) / sample_count

        # Bayesian smoothing: (successes + prior_weight * prior_rate) / (total + prior_weight)
        prior_weight = 5.0
        prior_success_rate = 0.85
        smoothed_success_rate = (successes + prior_weight * prior_success_rate) / (sample_count + prior_weight)

        return {
            "sample_count": sample_count,
            "raw_success_rate": raw_success_rate,
            "smoothed_success_rate": smoothed_success_rate,
            "avg_duration": avg_duration,
            "avg_cost": avg_cost,
            "has_sufficient_samples": sample_count >= 3,
        }

    def list_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent routing history records."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM router_history ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]
