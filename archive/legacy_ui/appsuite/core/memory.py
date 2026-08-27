"""Memory System - stores previous jobs, prompts, asset history, outcomes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..db import Database


class MemorySystem:
    def __init__(self, db: Database):
        self.db = db

    def remember(self, job_id: str, prompt: str, template_id: str, outcome: str,
                 summary: Dict[str, Any]) -> None:
        self.db.add_memory(job_id, prompt, template_id, outcome, summary)

    def recall(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.db.recall_memory(limit)

    def recall_similar(self, prompt: str) -> Optional[Dict[str, Any]]:
        return self.db.find_similar_prompt(prompt)