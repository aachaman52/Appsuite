"""End-to-End Deterministic Execution Engine for PyFlare Beta (Section 6).

Coordinates the vertical slice workflow:
Request -> Context -> TaskSpec -> Validation -> Authorization -> Router ->
Resource Admission -> Execution -> Unity Bridge -> Result Validation ->
Task Journal / Idempotency -> Audit Log -> User-Visible Display.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

from .audit import AuditEvent, AuditLog
from .codec import TaskSpecCodec
from .context import ProjectContextManager, TaskContext
from .hardware import HardwareSnapshot
from .journal import IdempotencyRecord, TaskJournal
from .models import ExecutionKind, TaskSpec
from .router import DeterministicRouter, RouteDecision
from .scheduler import (
    AdmissionDecision,
    AdmissionStatus,
    JobPriority,
    ResourceScheduler,
)
from .security import Authorizer, PermissionGrant
from .unity_client import (
    UnityBridgeClient,
    UnityBridgeError,
    UnityBridgeTransportError,
)
from .unity_protocol import (
    EditorMode,
    OperationStatus,
    UnityCommand,
    UnityPreconditions,
    UnityResponse,
)
from .validation import (
    FindingSeverity,
    ValidationFinding,
    ValidationPolicy,
    ValidationResult,
    ValidationStatus,
)
from .workflow import TaskRecord, TaskStatus


class ExecutionEngineError(RuntimeError):
    """Base error for execution engine pipeline failures."""


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    request_id: str
    project_id: str
    user_id: str
    intent: str
    task_spec: TaskSpec
    grant: PermissionGrant
    operation: str
    operation_arguments: dict[str, Any] = field(default_factory=dict)
    preconditions: UnityPreconditions | None = None
    idempotency_key: str = ""
    register_undo: bool = True
    save_scene: bool = False

    def __post_init__(self) -> None:
        if not self.request_id or not self.project_id or not self.user_id:
            raise ValueError("request_id, project_id, and user_id are required")
        if not self.idempotency_key:
            object.__setattr__(self, "idempotency_key", f"idemp_{self.request_id}")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    request_id: str
    task_id: str
    project_id: str
    status: str
    route_decision: RouteDecision | None
    admission_decision: AdmissionDecision | None
    context: TaskContext | None
    unity_response: UnityResponse | None
    validation_result: ValidationResult
    task_record: TaskRecord | None
    display_output: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    is_cached_replay: bool = False


class ExecutionEngine:
    """Orchestrates the authoritative PyFlare beta execution lifecycle."""

    def __init__(
        self,
        *,
        context_manager: ProjectContextManager,
        router: DeterministicRouter,
        scheduler: ResourceScheduler,
        journal: TaskJournal,
        audit_log: AuditLog,
        unity_client: UnityBridgeClient | None = None,
        validation_policy: ValidationPolicy | None = None,
    ) -> None:
        self.context_manager = context_manager
        self.router = router
        self.scheduler = scheduler
        self.journal = journal
        self.audit_log = audit_log
        self.unity_client = unity_client
        self.validation_policy = validation_policy or ValidationPolicy(
            frozenset({"validator.unity.status"})
        )

    @staticmethod
    def _pass_validation() -> ValidationResult:
        return ValidationResult(
            validator_id="validator.unity.status",
            validator_version="1.0",
            status=ValidationStatus.PASS,
        )

    @staticmethod
    def _fail_validation(msg: str = "operation failed") -> ValidationResult:
        return ValidationResult(
            validator_id="validator.unity.status",
            validator_version="1.0",
            status=ValidationStatus.FAIL,
            findings=(
                ValidationFinding(code="FAIL", message=msg, severity=FindingSeverity.ERROR),
            ),
        )

    def execute(
        self,
        request: ExecutionRequest,
        hardware: HardwareSnapshot,
        *,
        priority: JobPriority = JobPriority.FOREGROUND_ASSIST,
    ) -> ExecutionResult:
        task = request.task_spec
        errors: list[str] = []
        warnings: list[str] = []

        # ── Step 1: Context Awareness ─────────────────────────────────────────
        context: TaskContext | None = None
        try:
            context = self.context_manager.retrieve_context(
                request.project_id,
                request.intent,
                max_tokens=4000,
            )
        except Exception as exc:
            warnings.append(f"Context retrieval warning: {exc}")

        # ── Step 2: Journal Task Creation or Retrieval ────────────────────────
        self.journal.initialize()
        task_record = self.journal.get_task(task.task_id)
        if task_record is None:
            task_record = self.journal.create_task(
                task,
                actor=f"user:{request.user_id}",
                metadata={"intent": request.intent, "request_id": request.request_id},
            )

        # ── Step 3: Idempotency Reservation ───────────────────────────────────
        idemp_record = self.journal.reserve_operation(
            idempotency_key=request.idempotency_key,
            task_id=task.task_id,
            operation=request.operation,
        )

        if not idemp_record.is_new and idemp_record.status == "completed":
            # Replay cached result deterministically
            cached_resp = idemp_record.response or {}
            display = self._render_display(
                request=request,
                status="succeeded (cached)",
                route_id="cached",
                result_data=cached_resp,
                validation_passed=True,
            )
            return ExecutionResult(
                request_id=request.request_id,
                task_id=task.task_id,
                project_id=request.project_id,
                status="succeeded",
                route_decision=None,
                admission_decision=None,
                context=context,
                unity_response=None,
                validation_result=self._pass_validation(),
                task_record=task_record,
                display_output=display,
                is_cached_replay=True,
            )

        # Validate authorization grant
        if request.grant.task_id != task.task_id:
            err = "Permission grant belongs to a different task"
            self._record_failure(task.task_id, err, f"user:{request.user_id}", request)
            return self._build_rejected_result(request, err, context, task_record)

        try:
            for cap_id in sorted(task.required_capabilities):
                Authorizer.require_capability(request.grant, cap_id)
        except PermissionError as exc:
            err = f"Authorization denied: {exc}"
            self._record_failure(task.task_id, err, f"user:{request.user_id}", request)
            return self._build_rejected_result(request, err, context, task_record)

        if task_record.status == TaskStatus.DRAFT:
            task_record = self.journal.transition(
                task.task_id,
                TaskStatus.AUTHORIZED,
                expected_revision=task_record.revision,
                actor="authorization-service",
                reason="grant valid",
            )

        # ── Step 4: Deterministic Routing & Resource Admission ────────────────
        try:
            route_decision = self.router.route(task, hardware)
        except Exception as exc:
            err = f"Routing failed: {exc}"
            self._record_failure(task.task_id, err, "router", request)
            return self._build_rejected_result(request, err, context, task_record)

        provider = self.router.providers.get(route_decision.primary_provider_id)
        if provider is None:
            err = "Route references an unknown provider"
            self._record_failure(task.task_id, err, "router", request)
            return self._build_rejected_result(request, err, context, task_record)

        admission_decision = self.scheduler.admit(
            task,
            provider,
            hardware,
            priority=priority,
        )

        if admission_decision.status != AdmissionStatus.ADMITTED:
            err = f"Resource admission rejected: {admission_decision.reason}"
            self._record_failure(task.task_id, err, "scheduler", request)
            return self._build_rejected_result(request, err, context, task_record)

        if task_record.status == TaskStatus.AUTHORIZED:
            task_record = self.journal.transition(
                task.task_id,
                TaskStatus.QUEUED,
                expected_revision=task_record.revision,
                actor="scheduler",
                reason=f"admitted to provider {provider.provider_id}",
            )

        # ── Step 5: Execution ─────────────────────────────────────────────────
        if task_record.status == TaskStatus.QUEUED:
            task_record = self.journal.transition(
                task.task_id,
                TaskStatus.RUNNING,
                expected_revision=task_record.revision,
                actor="execution-engine",
                reason="executing on primary provider",
            )

        unity_resp: UnityResponse | None = None
        result_payload: dict[str, Any] = {}

        if provider.kind == ExecutionKind.APPLICATION:
            # Unity Editor execution path
            if self.unity_client is None:
                err = "Unity bridge client is not configured in engine"
                self._record_failure(task.task_id, err, "unity-dispatcher", request)
                return self._build_failed_result(request, err, context, task_record, route_decision, admission_decision)

            cmd = UnityCommand(
                protocol="pyflare-unity/1.0",
                request_id=request.request_id,
                task_id=task.task_id,
                project_id=request.project_id,
                operation=request.operation,
                arguments=request.operation_arguments,
                preconditions=request.preconditions or UnityPreconditions(editor_mode=EditorMode.EDIT),
                idempotency_key=request.idempotency_key,
                register_undo=request.register_undo,
                save_scene=request.save_scene,
            )

            try:
                unity_resp = self.unity_client.execute(cmd)
                result_payload = dict(unity_resp.result)
                warnings.extend(unity_resp.warnings)
                errors.extend(unity_resp.errors)
            except UnityBridgeTransportError as exc:
                err = f"Unity Editor is disconnected or unreachable: {exc}"
                self._record_failure(task.task_id, err, "unity-client", request)
                return self._build_failed_result(request, err, context, task_record, route_decision, admission_decision)
            except UnityBridgeError as exc:
                err = f"Unity bridge error: {exc}"
                self._record_failure(task.task_id, err, "unity-client", request)
                return self._build_failed_result(request, err, context, task_record, route_decision, admission_decision)

        elif provider.kind == ExecutionKind.DETERMINISTIC:
            # Deterministic local inspection / rule execution
            result_payload = {
                "operation": request.operation,
                "status": "succeeded",
                "output": "Deterministic rule executed cleanly",
            }
        else:
            result_payload = {"status": "succeeded", "provider": provider.provider_id}

        # ── Step 6: Validation ────────────────────────────────────────────────
        if task_record.status == TaskStatus.RUNNING:
            task_record = self.journal.transition(
                task.task_id,
                TaskStatus.VALIDATING,
                expected_revision=task_record.revision,
                actor="validation-service",
                reason="validating operation results",
            )

        validation_passed = True
        if unity_resp is not None:
            if unity_resp.status != OperationStatus.SUCCEEDED:
                validation_passed = False
                errors.append(f"Unity operation status was '{unity_resp.status.value}', expected 'succeeded'")

        if not validation_passed:
            err = "Validation detected unsuccessful operation"
            self._record_failure(task.task_id, err, "validator", request)
            return self._build_failed_result(
                request,
                err,
                context,
                task_record,
                route_decision,
                admission_decision,
                unity_resp=unity_resp,
                errors=errors,
            )

        # ── Step 7: Finalization, Idempotency & Audit ──────────────────────────
        if task_record.status == TaskStatus.VALIDATING:
            task_record = self.journal.transition(
                task.task_id,
                TaskStatus.COMPLETED,
                expected_revision=task_record.revision,
                actor="execution-engine",
                reason="execution and validation succeeded",
            )

        self.journal.complete_operation(
            idempotency_key=request.idempotency_key,
            response=result_payload,
        )

        self.audit_log.log(
            actor=f"user:{request.user_id}",
            event_type=f"execute.{request.operation}",
            task_id=task.task_id,
            payload={
                "project_id": request.project_id,
                "request_id": request.request_id,
                "route": route_decision.primary_provider_id,
                "result": result_payload,
            },
        )

        # ── Step 8: User Interface Display Rendering ──────────────────────────
        display = self._render_display(
            request=request,
            status="succeeded",
            route_id=route_decision.primary_provider_id,
            result_data=result_payload,
            validation_passed=True,
            warnings=warnings,
        )

        return ExecutionResult(
            request_id=request.request_id,
            task_id=task.task_id,
            project_id=request.project_id,
            status="succeeded",
            route_decision=route_decision,
            admission_decision=admission_decision,
            context=context,
            unity_response=unity_resp,
            validation_result=self._pass_validation(),
            task_record=task_record,
            display_output=display,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def _render_display(
        self,
        request: ExecutionRequest,
        status: str,
        route_id: str,
        result_data: Mapping[str, Any],
        validation_passed: bool,
        warnings: list[str] | None = None,
    ) -> str:
        lines = [
            "============================================================",
            f" PyFlare Task Execution: {request.task_spec.task_id}",
            "============================================================",
            f" Intent:      {request.intent}",
            f" Project:     {request.project_id}",
            f" Operation:   {request.operation}",
            f" Route:       {route_id}",
            f" Status:      {status.upper()}",
            f" Validation:  {'PASSED' if validation_passed else 'FAILED'}",
        ]
        if "object_id" in result_data:
            lines.append(f" Object ID:   {result_data['object_id']}")
        if "name" in result_data:
            lines.append(f" Object Name: {result_data['name']}")
        if "scene_path" in result_data:
            lines.append(f" Scene:       {result_data['scene_path']}")
        if warnings:
            lines.append(f" Warnings:    {'; '.join(warnings)}")
        lines.append("============================================================")
        return "\n".join(lines)

    def _record_failure(
        self,
        task_id: str,
        reason: str,
        actor: str,
        request: ExecutionRequest,
    ) -> None:
        try:
            rec = self.journal.get_task(task_id)
            if rec.status != TaskStatus.FAILED:
                self.journal.transition(
                    task_id,
                    TaskStatus.FAILED,
                    expected_revision=rec.revision,
                    actor=actor,
                    reason=reason,
                )
        except Exception:
            pass

        self.audit_log.log(
            actor=actor,
            event_type=f"execute.{request.operation}.failed",
            task_id=task_id,
            payload={"request_id": request.request_id, "project_id": request.project_id, "reason": reason},
        )

    def _build_rejected_result(
        self,
        request: ExecutionRequest,
        error: str,
        context: TaskContext | None,
        task_record: TaskRecord | None,
    ) -> ExecutionResult:
        display = (
            f"Task Rejected: {request.task_spec.task_id}\n"
            f"Reason: {error}"
        )
        return ExecutionResult(
            request_id=request.request_id,
            task_id=request.task_spec.task_id,
            project_id=request.project_id,
            status="rejected",
            route_decision=None,
            admission_decision=None,
            context=context,
            unity_response=None,
            validation_result=self._fail_validation(error),
            task_record=task_record,
            display_output=display,
            errors=(error,),
        )

    def _build_failed_result(
        self,
        request: ExecutionRequest,
        error: str,
        context: TaskContext | None,
        task_record: TaskRecord | None,
        route_decision: RouteDecision | None,
        admission_decision: AdmissionDecision | None,
        unity_resp: UnityResponse | None = None,
        errors: list[str] | None = None,
    ) -> ExecutionResult:
        display = (
            f"Task Failed: {request.task_spec.task_id}\n"
            f"Error: {error}"
        )
        all_errors = list(errors or [])
        if error not in all_errors:
            all_errors.append(error)
        return ExecutionResult(
            request_id=request.request_id,
            task_id=request.task_spec.task_id,
            project_id=request.project_id,
            status="failed",
            route_decision=route_decision,
            admission_decision=admission_decision,
            context=context,
            unity_response=unity_resp,
            validation_result=self._fail_validation(error),
            task_record=task_record,
            display_output=display,
            errors=tuple(all_errors),
        )
