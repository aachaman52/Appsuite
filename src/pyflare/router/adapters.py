"""Real worker and provider execution adapters for PyFlare Deterministic Router."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, Optional

from pyflare.router.models import RouteCandidate, TaskSpec, TaskType


def sanitize_error_message(msg: str) -> str:
    """Strip secret keys, tokens, passwords, and internal credentials from error strings."""
    if not msg:
        return ""
    # Strip OpenAI / Gemini / Anthropic / generic API keys and bearer tokens
    cleaned = re.sub(r"(sk-[a-zA-Z0-9_-]{15,})", "[REDACTED_KEY]", str(msg))
    cleaned = re.sub(r"(AIza[a-zA-Z0-9_-]{15,})", "[REDACTED_KEY]", cleaned)
    cleaned = re.sub(r"(Bearer\s+[a-zA-Z0-9_.-]+)", "Bearer [REDACTED]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(key=[a-zA-Z0-9_-]+)", "key=[REDACTED]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(token=[a-zA-Z0-9_.-]+)", "token=[REDACTED]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(password=[^\s&]+)", "password=[REDACTED]", cleaned, flags=re.IGNORECASE)
    return cleaned


class RouterExecutionError(Exception):
    """Base exception for router execution errors with retryable classification."""
    def __init__(
        self,
        message: str,
        is_retryable: bool = False,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        clean_msg = sanitize_error_message(message)
        super().__init__(clean_msg)
        self.message = clean_msg
        self.is_retryable = is_retryable
        self.reason = sanitize_error_message(reason)
        self.metadata = metadata or {}


class AdapterUnavailableError(RouterExecutionError):
    """Raised when no execution adapter exists for a route candidate."""
    def __init__(self, message: str) -> None:
        super().__init__(message, is_retryable=False)


class ExecutionTimeoutError(RouterExecutionError, TimeoutError):
    """Raised when candidate execution exceeds the timeout limit."""
    def __init__(self, message: str, is_retryable: bool = True) -> None:
        super().__init__(message, is_retryable=is_retryable)


class WorkerExecutionError(RouterExecutionError):
    """Raised when an execution worker returns a failed or error result."""
    def __init__(
        self,
        message: str,
        is_retryable: bool = True,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, is_retryable=is_retryable, reason=reason, metadata=metadata)


class WorkerValidationError(RouterExecutionError):
    """Raised when validation fails or asset verification is rejected."""
    def __init__(
        self,
        message: str,
        is_retryable: bool = False,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, is_retryable=is_retryable, reason=reason, metadata=metadata)


class ProviderExecutionError(RouterExecutionError):
    """Raised when an LLM provider encounters an execution or API error."""
    def __init__(
        self,
        message: str,
        is_retryable: bool = True,
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, is_retryable=is_retryable, reason=reason, metadata=metadata)


class UnsupportedTaskError(RouterExecutionError):
    """Raised when a candidate or rule engine cannot perform the requested task type."""
    def __init__(self, message: str) -> None:
        super().__init__(message, is_retryable=False)


def create_code_worker_adapter(code_worker: Any) -> Any:
    """Adapter connecting router to CodeWorker with strict contract validation."""
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        job = {
            "id": task.task_id,
            "prompt": task.prompt,
            "template_id": task.metadata.get("template_id", "default"),
        }
        state = {
            "project_path": task.metadata.get("project_path"),
            "assets": task.metadata.get("assets", []),
        }
        res = code_worker.run(job, state)
        if res is None:
            raise WorkerExecutionError("CodeWorker returned null/empty response", is_retryable=True)

        status_val = getattr(res.status, "value", str(res.status)).lower()
        if status_val not in ("success", "ok"):
            err_reason = getattr(res, "reason", "Worker execution status was not success")
            raise WorkerExecutionError(
                f"CodeWorker failed with status '{status_val}': {err_reason}",
                is_retryable=True,
                reason=err_reason,
                metadata=getattr(res, "metadata", {}),
            )

        return {
            "status": "success",
            "candidate_id": candidate.candidate_id,
            "worker": "code",
            "data": getattr(res, "data", {}),
            "reason": getattr(res, "reason", "ok"),
            "metadata": getattr(res, "metadata", {}),
        }
    return _adapter


def create_blender_worker_adapter(blender_worker: Any) -> Any:
    """Adapter connecting router to BlenderWorker with strict contract validation."""
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        job = {
            "id": task.task_id,
            "prompt": task.prompt,
            "template_id": task.metadata.get("template_id", "default"),
        }
        state = {
            "project_path": task.metadata.get("project_path"),
            "assets": task.metadata.get("assets", []),
        }
        res = blender_worker.run(job, state)
        if res is None:
            raise WorkerExecutionError("BlenderWorker returned null response", is_retryable=True)

        status_val = getattr(res.status, "value", str(res.status)).lower()
        if status_val not in ("success", "ok"):
            err_reason = getattr(res, "reason", "Blender execution was not successful")
            raise WorkerExecutionError(
                f"BlenderWorker failed with status '{status_val}': {err_reason}",
                is_retryable=True,
                reason=err_reason,
                metadata=getattr(res, "metadata", {}),
            )

        return {
            "status": "success",
            "candidate_id": candidate.candidate_id,
            "worker": "blender",
            "data": getattr(res, "data", {}),
            "reason": getattr(res, "reason", "ok"),
            "metadata": getattr(res, "metadata", {}),
        }
    return _adapter


def create_godot_worker_adapter(godot_worker: Any) -> Any:
    """Adapter connecting router to GodotWorker with strict contract validation."""
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        job = {
            "id": task.task_id,
            "prompt": task.prompt,
            "template_id": task.metadata.get("template_id", "default"),
        }
        state = {
            "project_path": task.metadata.get("project_path"),
            "assets": task.metadata.get("assets", []),
        }
        res = godot_worker.run(job, state)
        if res is None:
            raise WorkerExecutionError("GodotWorker returned null response", is_retryable=True)

        status_val = getattr(res.status, "value", str(res.status)).lower()
        if status_val not in ("success", "ok"):
            err_reason = getattr(res, "reason", "Godot worker failed")
            raise WorkerExecutionError(
                f"GodotWorker failed with status '{status_val}': {err_reason}",
                is_retryable=True,
                reason=err_reason,
                metadata=getattr(res, "metadata", {}),
            )

        return {
            "status": "success",
            "candidate_id": candidate.candidate_id,
            "worker": "godot",
            "data": getattr(res, "data", {}),
            "reason": getattr(res, "reason", "ok"),
            "metadata": getattr(res, "metadata", {}),
        }
    return _adapter


def create_validation_worker_adapter(validation_worker: Any) -> Any:
    """Adapter connecting router to ValidationWorker with strict contract validation."""
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        job = {
            "id": task.task_id,
            "prompt": task.prompt,
            "template_id": task.metadata.get("template_id", "default"),
        }
        state = {
            "project_path": task.metadata.get("project_path"),
            "assets": task.metadata.get("assets", []),
            "generated_scripts": task.metadata.get("generated_scripts", []),
        }
        res = validation_worker.run(job, state)
        if res is None:
            raise WorkerValidationError("ValidationWorker returned null response", is_retryable=False)

        status_val = getattr(res.status, "value", str(res.status)).lower()
        if status_val not in ("success", "ok"):
            err_reason = getattr(res, "reason", "Validation check failed")
            raise WorkerValidationError(
                f"ValidationWorker failed with status '{status_val}': {err_reason}",
                is_retryable=False,
                reason=err_reason,
                metadata=getattr(res, "metadata", {}),
            )

        return {
            "status": "success",
            "candidate_id": candidate.candidate_id,
            "worker": "validation",
            "data": getattr(res, "data", {}),
            "reason": getattr(res, "reason", "ok"),
            "metadata": getattr(res, "metadata", {}),
        }
    return _adapter


def create_provider_manager_adapter(provider_manager: Any) -> Any:
    """Adapter connecting router to ProviderManager for cloud/local LLMs."""
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        task_type_str = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
        try:
            output_text = provider_manager.generate_text(
                prompt=task.prompt,
                task_type=task_type_str,
                timeout=task.preferred_latency_seconds or 30.0,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            is_non_retryable = any(k in err_str for k in ("401", "403", "unauthorized", "invalid api key", "permission denied"))
            raise ProviderExecutionError(
                f"Provider {candidate.candidate_id} failed: {exc}",
                is_retryable=not is_non_retryable,
                reason=str(exc),
            ) from exc

        if not output_text or not str(output_text).strip():
            raise ProviderExecutionError(
                f"Provider {candidate.candidate_id} returned empty text response",
                is_retryable=True,
            )

        return {
            "status": "success",
            "candidate_id": candidate.candidate_id,
            "provider_type": candidate.provider_type,
            "output": output_text,
        }
    return _adapter


def create_rule_engine_adapter() -> Any:
    """
    Honest deterministic rule-based adapter.
    Performs real local checks (AST parsing, file existence) and planning.
    Never fakes completed software generation or unconditional validation.
    """
    def _adapter(task: TaskSpec, candidate: RouteCandidate) -> Dict[str, Any]:
        prompt = task.prompt
        task_type = task.task_type

        # 1. Real validation check
        if task_type == TaskType.VALIDATION:
            code_snippet = task.metadata.get("code")
            file_path = task.metadata.get("file_path")

            if code_snippet:
                try:
                    ast.parse(code_snippet)
                    return {
                        "status": "success",
                        "candidate_id": candidate.candidate_id,
                        "validation_passed": True,
                        "check_type": "python_ast_syntax",
                    }
                except SyntaxError as syn_err:
                    raise WorkerValidationError(
                        f"Python syntax validation failed: {syn_err.msg} at line {syn_err.lineno}",
                        is_retryable=False,
                        reason=str(syn_err),
                    )
            elif file_path:
                p = Path(file_path)
                if not p.exists():
                    raise WorkerValidationError(
                        f"File existence validation failed: '{file_path}' does not exist",
                        is_retryable=False,
                        reason="file_not_found",
                    )
                return {
                    "status": "success",
                    "candidate_id": candidate.candidate_id,
                    "validation_passed": True,
                    "check_type": "file_existence",
                    "file_size_bytes": p.stat().st_size,
                }
            else:
                raise UnsupportedTaskError(
                    "Deterministic rule validator requires 'code' or 'file_path' in task metadata."
                )

        # 2. Real deterministic classification / planning
        elif task_type in (TaskType.RESEARCH, TaskType.GENERAL):
            return {
                "status": "success",
                "candidate_id": candidate.candidate_id,
                "action": "task_plan",
                "plan_steps": [
                    f"Analyze prompt: '{prompt}'",
                    "Inspect system requirements and dependencies",
                    "Route to specialized execution worker",
                ],
            }

        # 3. Reject fake generation attempts honestly
        else:
            raise UnsupportedTaskError(
                f"Deterministic rule engine cannot generate code or synthesis assets from scratch for '{task_type.value}'"
            )

    return _adapter
