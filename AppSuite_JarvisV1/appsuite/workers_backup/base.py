"""Base worker class with retry/backoff and structured logging."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict

from ..logging_setup import get_logger


class WorkerError(Exception):
    """Raised when a worker permanently fails a task."""


class BaseWorker:
    name: str = "base"

    def __init__(self, config: Dict[str, Any], retries: Dict[str, Any], context: Dict[str, Any]):
        self.config = config
        self.retries = retries
        self.context = context
        self.log = get_logger(f"worker.{self.name}")

    def with_retry(self, fn: Callable[[], Any], desc: str = "") -> Any:
        max_attempts = int(self.retries.get("max_attempts", 3))
        backoff = float(self.retries.get("backoff_seconds", 2.0))
        mult = float(self.retries.get("backoff_multiplier", 2.0))
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.log.warning("%s attempt %d/%d failed: %s", desc or self.name,
                                 attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= mult
        raise WorkerError(f"{desc or self.name} failed after {max_attempts} attempts: {last_exc}")

    def run(self, job: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError