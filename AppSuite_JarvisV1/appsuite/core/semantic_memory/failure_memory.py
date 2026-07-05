from __future__ import annotations
from typing import Any, Dict, List

class FailureMemory:
    """Stores known failures and recovery strategies in SQLite database."""
    def __init__(self, db=None):
        self.db = db
        self._local_failures = []

    def log_failure(self, error_or_prompt: str, context_or_error: Any = None, context: Dict[str, Any] = None):
        if context is not None:
            prompt = error_or_prompt
            error = context_or_error
            ctx = context
        else:
            prompt = "default_prompt"
            error = error_or_prompt
            ctx = context_or_error or {}

        if self.db and hasattr(self.db, "add_failure_memory"):
            self.db.add_failure_memory(prompt, error, ctx)
        else:
            self._local_failures.append({"prompt": prompt, "error": error, "context": ctx})

    def get_failures_for_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        if self.db and hasattr(self.db, "get_failure_memories"):
            return self.db.get_failure_memories(prompt)
        return [f for f in self._local_failures if f["prompt"] == prompt]
