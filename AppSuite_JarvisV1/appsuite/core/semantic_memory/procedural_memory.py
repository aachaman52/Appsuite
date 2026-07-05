from __future__ import annotations
from typing import Any, Dict, List
import time
from .embedding_client import EmbeddingClient

class ProceduralMemory:
    """Stores recipes and execution guidelines based on task type and details."""
    def __init__(self, db=None, provider_manager=None):
        self.db = db
        self._local = []
        self.client = EmbeddingClient(db, provider_manager)

    def add_recipe(self, task_type: str, recipe: Dict[str, Any], outcome: str = "success"):
        if self.db and hasattr(self.db, "add_procedural_memory"):
            self.db.add_procedural_memory(task_type, recipe, outcome)
        else:
            self._local.append({
                "task_type": task_type,
                "recipe": recipe,
                "outcome": outcome,
                "created_at": time.time()
            })

    def get_recipes(self, task_type: str, limit: int = 5) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "get_procedural_memories"):
            return self.db.get_procedural_memories(task_type, limit)
        else:
            return [r for r in self._local if r["task_type"] == task_type][:limit]
