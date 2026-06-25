from __future__ import annotations

class FailureMemory:
    """Stores known failures and recovery strategies."""
    def __init__(self):
        self.failures = []

    def log_failure(self, error: str, context: dict):
        self.failures.append({"error": error, "context": context})
