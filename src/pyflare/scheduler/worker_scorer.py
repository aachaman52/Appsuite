"""Compute worker quality scores from historical strategy memory."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from ..memory.semantic_memory import SemanticMemory


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
                stats = db.list_worker_stats() if hasattr(db, "list_worker_stats") else []
                for row in stats:
                    worker = row.get("worker", "")
                    succ = row.get("success_count", 0)
                    fail = row.get("failure_count", 0)
                    total = succ + fail
                    if total > 0:
                        scores[worker] = succ / total
        except Exception:
            pass

        return scores


WorkerScorer = WorkerScoreRegistry
