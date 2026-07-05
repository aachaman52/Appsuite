from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
from .job_state import UnifiedJobState
from ..core.state import WorkerResult

class WorkerProtocol(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the worker/plugin resources. Returns True if successful."""
        pass

    @abstractmethod
    def health_check(self) -> Tuple[bool, str]:
        """Verify the health/availability of the worker. Returns (is_healthy, status_message)."""
        pass

    @abstractmethod
    def process(self, job: Dict[str, Any], state: UnifiedJobState) -> WorkerResult:
        """Run the main task process."""
        pass

    @abstractmethod
    def checkpoint(self, state: UnifiedJobState) -> Dict[str, Any]:
        """Save a snapshot of the worker state."""
        pass

    @abstractmethod
    def resume(self, checkpoint: Dict[str, Any], state: UnifiedJobState) -> None:
        """Resume execution from a checkpoint."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup worker resources."""
        pass
