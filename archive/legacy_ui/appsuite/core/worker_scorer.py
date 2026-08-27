"""Compute worker quality scores from historical strategy memory."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from .semantic_memory import SemanticMemory


class WorkerScoreRegistry:
    def __init__(self, memory: Optional[SemanticMemory] = None):
        self.memory = memory

    def _normalize(self, value: float, scale: float = 1.0) -> float:
        return float(value) / scale if scale else 0.0

    def score_workers(self) -> Dict[str, float]:
        if not self.memory or not getattr(self.memory, "strategy", None):
            return {}

        scores: Dict[str, float] = {}
        try:
            db = getattr(self.memory.strategy, "db", None)
            if db:
                rows = db.query("SELECT * FROM strategy_memory")
            else:
                rows = self.memory.strategy.get_strategies_for_prompt("")
        except Exception:
            rows = []

        for row in rows:
            strategy = None
            if isinstance(row, dict) and row.get("strategy"):
                strategy = row["strategy"]
            else:
                try:
                    strategy = json.loads(row.get("strategy_json", "{}"))
                except Exception:
                    continue
            worker = strategy.get("worker") or strategy.get("agent") or strategy.get("agent_name")
            if not worker:
                continue
            weight = 1.0 if row.get("outcome") == "success" else -0.5
            scores[worker] = scores.get(worker, 0.0) + weight

        if not scores:
            return {}

        max_abs = max(abs(v) for v in scores.values()) or 1.0
        return {k: self._normalize(v, max_abs) for k, v in scores.items()}

    def get_score(self, worker_name: str) -> float:
        return self.score_workers().get(worker_name, 0.0)
