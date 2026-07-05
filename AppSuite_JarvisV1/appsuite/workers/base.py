"""Base worker class with retry/backoff and structured logging."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple, List

from ..logging_setup import get_logger
from ..engine.worker_protocol import WorkerProtocol
from ..core.state import WorkerResult, WorkerStatus


class WorkerError(Exception):
    """Raised when a worker permanently fails a task."""


class BaseWorker(WorkerProtocol):
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

    def initialize(self) -> bool:
        return True

    def health_check(self) -> Tuple[bool, str]:
        from ..core.health import WorkerHealthMonitor
        return WorkerHealthMonitor.preflight_check(self.name)

    def plan(self, job: Dict[str, Any], state: Any) -> List[str]:
        return [self.name]

    def verify(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> Tuple[bool, str]:
        if result.status == WorkerStatus.SUCCESS:
            return True, "ok"
        return False, f"status: {result.status.value}"

    def recover(self, job: Dict[str, Any], state: Any, exception: Exception) -> WorkerResult:
        self.log.error("[%s] Default recovery path: raising error: %s", self.name, exception)
        raise exception

    def cleanup(self) -> None:
        pass

    def checkpoint(self, state: Any) -> Dict[str, Any]:
        return {}

    def resume(self, checkpoint: Dict[str, Any], state: Any) -> None:
        pass

    def report(self, job: Dict[str, Any], state: Any) -> Dict[str, Any]:
        return {
            "worker": self.name,
            "status": "healthy",
            "timestamp": time.time()
        }

    def learn_strategy(self, job: Dict[str, Any], state: Any, result: WorkerResult) -> None:
        db = self.context.get("db")
        if not db:
            return
        from ..core.semantic_memory import SemanticMemory
        try:
            mem = SemanticMemory(db)
            strategy_info = {
                "worker": self.name,
                "job_id": job.get("id"),
                "prompt": job.get("prompt"),
                "outcome": result.status.value,
                "reason": result.reason,
                "metadata": result.metadata
            }
            mem.strategy.add_strategy(
                prompt=f"worker_run:{self.name}:{job.get('prompt')}",
                strategy=strategy_info,
                outcome="success" if result.status == WorkerStatus.SUCCESS else "failed"
            )
            self.log.info("[%s] Learned successful execution strategy stored in SemanticMemory", self.name)
        except Exception as exc:
            self.log.warning("[%s] Failed to store strategy in SemanticMemory: %s", self.name, exc)

    def process(self, job: Dict[str, Any], state: Any) -> WorkerResult:
        self.initialize()
        
        ok, msg = self.health_check()
        health_failed = not ok
        if health_failed:
            self.log.warning("[%s] Health check failed: %s. Attempting recovery.", self.name, msg)
            try:
                result = self.recover(job, state, WorkerError(f"Health check failed: {msg}"))
            except Exception as rec_exc:
                self.log.error("[%s] Health recovery failed: %s", self.name, rec_exc)
                return WorkerResult(
                    status=WorkerStatus.FAILED,
                    data={},
                    reason=f"Health check failed: {msg} (Recovery failed: {rec_exc})",
                    metadata={"error": str(rec_exc)}
                )
        else:
            subtasks = self.plan(job, state)
            self.log.info("[%s] Starting process with plan: %s", self.name, subtasks)
            
            try:
                result = self.run(job, state)
            except Exception as exc:
                self.log.warning("[%s] Run failed: %s. Attempting recovery.", self.name, exc)
                try:
                    result = self.recover(job, state, exc)
                except Exception as rec_exc:
                    self.log.error("[%s] Recovery failed: %s", self.name, rec_exc)
                    return WorkerResult(
                        status=WorkerStatus.FAILED,
                        data={},
                        reason=f"Execution & Recovery failed: {rec_exc}",
                        metadata={"error": str(rec_exc)}
                    )

        is_valid, v_msg = self.verify(job, state, result)
        if not is_valid:
            self.log.warning("[%s] Verification failed: %s. Attempting recovery.", self.name, v_msg)
            try:
                result = self.recover(job, state, WorkerError(f"Verification failed: {v_msg}"))
                # Re-verify after recovery
                is_valid, v_msg = self.verify(job, state, result)
                if not is_valid:
                    reason_msg = f"Health check failed: {msg}" if health_failed else f"Verification failed after recovery: {v_msg}"
                    return WorkerResult(
                        status=WorkerStatus.FAILED,
                        data={},
                        reason=reason_msg,
                        metadata={}
                    )
            except Exception as rec_exc:
                self.log.error("[%s] Verification recovery failed: %s", self.name, rec_exc)
                reason_msg = f"Health check failed: {msg}" if health_failed else f"Verification recovery failed: {rec_exc}"
                return WorkerResult(
                    status=WorkerStatus.FAILED,
                    data={},
                    reason=reason_msg,
                    metadata={"error": str(rec_exc)}
                )

        self.learn_strategy(job, state, result)
        self.cleanup()
        
        metrics = self.report(job, state)
        if not result.metadata:
            result.metadata = {}
        result.metadata["metrics"] = metrics

        world_model = None
        if isinstance(state, dict):
            world_model = state.get("world_model")
        else:
            world_model = getattr(state, "world_model", None)

        if world_model and hasattr(world_model, "update"):
            try:
                world_model.update(self.name, {
                    "status": result.status.value,
                    "data": result.data,
                    "reason": result.reason,
                    "metadata": result.metadata,
                    "timestamp": time.time()
                })
            except Exception as exc:
                self.log.warning("[%s] world_model.update failed: %s", self.name, exc)

        return result

    def run(self, job: Dict[str, Any], state: Any) -> WorkerResult:
        raise NotImplementedError