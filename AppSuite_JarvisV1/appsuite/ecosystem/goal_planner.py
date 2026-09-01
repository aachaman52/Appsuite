"""Jarvis Multi-Step Goal Planner v2 (Beta Execution Safety Hardened).

Decomposes high-level user goals into structured sequences of safe ecosystem steps:
- Grounded in live read facts from canonical read tools (errors != empty results)
- Step types: read_summary, suggestion, write_action
- Strict per-step review, confirmation, editing, and skipping
- Unique per-step idempotency key assigned only on user confirmation
- Coordinated via OS-level PlanLock across multiple local sessions
- Fail-closed ownership isolation and pre-dispatch verification
- Non-retryable recovery_rejected lifecycle state
- Zero planning side-effects prior to explicit confirmation
"""
from __future__ import annotations

import datetime
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .action_validation import (
    WRITE_ACTION_COMMAND_IDS,
    validate_action_parameters,
)
from .client import AachmanEcosystemClient, get_ecosystem_client
from .constants import (
    HACKATHON_PROBLEMS,
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
    JARVIS_ALLOWED_READ_TOOL_IDS,
)
from .executor import EcosystemExecutor, ExecutionResult
from .interpreter import JarvisEcosystemIntent
from .planning_helpers import (
    calculate_exam_revision_schedule,
    is_duplicate_task,
    normalize_subject,
)
from .read_executor import EcosystemReadExecutor, JarvisReadResponse
from .read_interpreter import (
    JarvisReadIntent,
    get_current_date_kolkata,
    interpret_ecosystem_read_query,
)
from .plan_store import (
    PlanStore,
    PlanLock,
    PlanLockTimeoutError,
    CURRENT_SCHEMA_VERSION,
    VALID_STEP_STATUSES,
    get_current_timestamp_iso,
    compute_confirmation_fingerprint,
)
from ..logging_setup import get_logger

log = get_logger("ecosystem.goal_planner")


@dataclass
class GoalPlanStep:
    """A single logical step within a multi-step goal plan."""
    step_id: str
    order: int
    title: str
    description: str
    step_type: str  # "read_summary" | "suggestion" | "write_action"
    command_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    requires_confirmation: bool = False
    status: str = "planned"  # "planned" | "ready" | "confirmed" | "executing" | "completed" | "skipped" | "cancelled" | "failed" | "blocked" | "recovery_pending" | "recovery_rejected"
    depends_on: List[str] = field(default_factory=list)
    idempotency_key: Optional[str] = None
    confirmation_fingerprint: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "order": self.order,
            "title": self.title,
            "description": self.description,
            "step_type": self.step_type,
            "command_id": self.command_id,
            "parameters": self.parameters,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status,
            "depends_on": self.depends_on,
            "idempotency_key": self.idempotency_key,
            "confirmation_fingerprint": self.confirmation_fingerprint,
            "result": self.result,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GoalPlanStep:
        return cls(
            step_id=data.get("step_id", ""),
            order=data.get("order", 1),
            title=data.get("title", ""),
            description=data.get("description", ""),
            step_type=data.get("step_type", "suggestion"),
            command_id=data.get("command_id"),
            parameters=data.get("parameters", {}),
            reason=data.get("reason", ""),
            requires_confirmation=data.get("requires_confirmation", False),
            status=data.get("status", "planned"),
            depends_on=data.get("depends_on", []),
            idempotency_key=data.get("idempotency_key"),
            confirmation_fingerprint=data.get("confirmation_fingerprint"),
            result=data.get("result"),
            error_message=data.get("error_message"),
        )


@dataclass
class GoalPlan:
    """Structured representation of a multi-step goal plan."""
    goal: str
    summary: str
    source_tool_ids: List[str]
    steps: List[GoalPlanStep]
    confidence: float = 1.0
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    owner_id: Optional[str] = None
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: str = field(default_factory=get_current_timestamp_iso)
    updated_at: str = field(default_factory=get_current_timestamp_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "owner_id": self.owner_id,
            "goal": self.goal,
            "summary": self.summary,
            "source_tool_ids": self.source_tool_ids,
            "steps": [s.to_dict() for s in self.steps],
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GoalPlan:
        steps_data = data.get("steps", [])
        steps = [GoalPlanStep.from_dict(s) for s in steps_data if isinstance(s, dict)]
        return cls(
            goal=data.get("goal", ""),
            summary=data.get("summary", ""),
            source_tool_ids=data.get("source_tool_ids", []),
            steps=steps,
            confidence=data.get("confidence", 1.0),
            plan_id=data.get("plan_id", str(uuid.uuid4())),
            owner_id=data.get("owner_id"),
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
            created_at=data.get("created_at", get_current_timestamp_iso()),
            updated_at=data.get("updated_at", get_current_timestamp_iso()),
        )

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def total_write_steps(self) -> int:
        return sum(1 for s in self.steps if s.step_type == "write_action")

    @property
    def is_active(self) -> bool:
        return any(
            s.status in ("ready", "planned", "executing", "recovery_pending", "failed", "blocked")
            for s in self.steps
        )


class GoalPlanner:
    """Constructs and coordinates multi-step plans grounded in real ecosystem data."""

    def __init__(
        self,
        client: Optional[AachmanEcosystemClient] = None,
        read_executor: Optional[EcosystemReadExecutor] = None,
        executor: Optional[EcosystemExecutor] = None,
        plan_store: Optional[PlanStore] = None,
    ):
        self.read_executor = read_executor or EcosystemReadExecutor(client)
        self.client = client or (self.read_executor.client if self.read_executor else get_ecosystem_client())
        self.executor = executor or EcosystemExecutor(self.client)
        self.plan_store = plan_store or PlanStore()
        self._in_memory_plan_cache: Dict[str, GoalPlan] = {}

    def invalidate_plan_cache(self) -> None:
        """Clear cached in-memory plans on sign-out or account switch."""
        self._in_memory_plan_cache.clear()

    def plan_goal(
        self, prompt: str, now: Optional[datetime.datetime] = None
    ) -> Optional[GoalPlan]:
        """Parse high-level user goal, perform reads, and assemble sequenced steps."""
        if not prompt or not isinstance(prompt, str):
            return None

        cleaned = prompt.strip().lower()

        # Reject prompt injection or arbitrary SQL
        if any(p in cleaned for p in ("select * from", "insert into", "delete from", "drop table", "ignore rules")):
            return None

        res_plan = None
        # ── 1. Exam Preparation Goal ──
        if (
            re.search(r"\b(prepare|study|plan)\b.*\b(exam|finals|test)\b", cleaned)
            or re.search(r"\bprepare me for (my )?(next )?exam\b", cleaned)
            or re.search(r"\bprepare for finals week\b", cleaned)
        ):
            res_plan = self._plan_exam_preparation(now)

        # ── 2. Cricket Match / Rematch Goal ──
        elif (
            re.search(r"\b(set up|plan|create)\b.*\b(rematch|weekend match|cricket match)\b", cleaned)
            or re.search(r"\bset up a (weekend )?cricket match\b", cleaned)
            or re.search(r"\bcreate a rematch plan\b", cleaned)
        ):
            res_plan = self._plan_cricket_goal(cleaned)

        # ── 3. Hackathon Practice Goal ──
        elif (
            re.search(r"\b(practice|prepare|train)\b.*\b(hackathon|challenge)\b", cleaned)
            or re.search(r"\bhelp me practice for (another )?hackathon\b", cleaned)
        ):
            res_plan = self._plan_hackathon_goal()

        if res_plan and res_plan.steps:
            res_plan.owner_id = self.client.user_id if self.client.is_authenticated else None
            try:
                self.plan_store.save_plan(res_plan.to_dict())
                self._in_memory_plan_cache[res_plan.plan_id] = res_plan
            except Exception as e:
                log.warning("Could not auto-persist plan %s: %s", res_plan.plan_id, e)

        return res_plan

    # ── Goal Plan Generators ──────────────────────────────────────────────────

    def _plan_exam_preparation(self, now: Optional[datetime.datetime] = None) -> GoalPlan:
        """Construct multi-step study plan for upcoming exams with verified read grounding."""
        if not self.client.is_authenticated:
            return GoalPlan(
                goal="Prepare for upcoming exams",
                summary="Sign in to your Aachman Account to create a personalized exam study plan.",
                source_tool_ids=[],
                steps=[],
                confidence=0.0,
            )

        ref_dt = get_current_date_kolkata(now)
        today_str = ref_dt.strftime("%Y-%m-%d")
        tom_str = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # Read upcoming exam
        res_exam = self.read_executor.execute_read_intent(
            JarvisReadIntent(tool_id="read.daymentor.next_exam", confidence=1.0)
        )

        # Handle read failure explicitly (Read failure != empty result)
        if res_exam.status in ("error", "failed"):
            log.warning("Exam read failed: %s", res_exam.human_text)
            return GoalPlan(
                goal="Prepare for upcoming exams",
                summary="I couldn't check your upcoming exams right now. Please check DayMentor connection and try again.",
                source_tool_ids=["read.daymentor.next_exam"],
                steps=[
                    GoalPlanStep(
                        step_id="step_01",
                        order=1,
                        title="Exam Schedule Check Unavailable",
                        description=f"DayMentor exam read returned an error: {res_exam.human_text}",
                        step_type="read_summary",
                        status="completed",
                    )
                ],
                confidence=0.0,
            )

        sources = ["read.daymentor.next_exam"]

        if res_exam.status == "success" and res_exam.data.get("has_exam"):
            exam = res_exam.data.get("exam", {})
            schedule = calculate_exam_revision_schedule(res_exam.data, ref_dt)
            subject = schedule["subject"]
            exam_date = schedule["exam_date"]
            days_rem = schedule["days_remaining"]

            # Read today's tasks for deduplication
            res_tasks_today = self.read_executor.execute_read_intent(
                JarvisReadIntent(
                    tool_id="read.daymentor.tasks_today",
                    confidence=1.0,
                    parameters={"target_date": today_str},
                )
            )
            sources.append("read.daymentor.tasks_today")

            # If revision is due tomorrow, ALSO read tomorrow's tasks for deduplication
            tasks_to_check: List[Dict[str, Any]] = []
            if res_tasks_today.status == "success":
                tasks_to_check.extend(res_tasks_today.data.get("tasks", []))
            elif res_tasks_today.status in ("error", "failed"):
                log.warning("Today's tasks read failed: %s", res_tasks_today.human_text)

            if schedule["revision_deadline"] == tom_str:
                res_tasks_tom = self.read_executor.execute_read_intent(
                    JarvisReadIntent(
                        tool_id="read.daymentor.tasks_tomorrow",
                        confidence=1.0,
                        parameters={"target_date": tom_str},
                    )
                )
                sources.append("read.daymentor.tasks_tomorrow")
                if res_tasks_tom.status == "success":
                    tasks_to_check.extend(res_tasks_tom.data.get("tasks", []))

            steps: List[GoalPlanStep] = []

            # Step 1: Read Summary
            urgency_text = "today" if days_rem == 0 else f"{days_rem} days remaining"
            steps.append(
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title=f"Review {subject} Exam Schedule",
                    description=f"Exam scheduled on {exam_date} ({urgency_text}).",
                    step_type="read_summary",
                    reason="Confirm exam timeline and urgency",
                    requires_confirmation=False,
                    status="completed",
                )
            )

            # Step 2: Primary Revision Task
            rev_title = schedule["revision_title"]
            if not is_duplicate_task(rev_title, tasks_to_check):
                pri = schedule["revision_priority"]
                deadline = schedule["revision_deadline"]
                steps.append(
                    GoalPlanStep(
                        step_id="step_02",
                        order=2,
                        title=f"Create {subject} Revision Task",
                        description=f"Core concepts review ({pri.capitalize()} priority due {deadline}).",
                        step_type="write_action",
                        command_id="action.daymentor.create_task",
                        parameters={"title": rev_title, "priority": pri, "deadline": deadline},
                        reason=f"Covers key syllabus topics before {exam_date}",
                        requires_confirmation=True,
                        status="ready",
                        depends_on=["step_01"],
                    )
                )

            # Step 3: Practice Problem Set (if >= 3 days away)
            if schedule["has_practice"]:
                prac_title = schedule["practice_title"]
                if not is_duplicate_task(prac_title, tasks_to_check):
                    prac_deadline = schedule["practice_deadline"]
                    steps.append(
                        GoalPlanStep(
                            step_id="step_03",
                            order=len(steps) + 1,
                            title=f"Create {subject} Practice Task",
                            description=f"Solve mock questions and practice problems (due {prac_deadline}).",
                            step_type="write_action",
                            command_id="action.daymentor.create_task",
                            parameters={"title": prac_title, "priority": schedule["practice_priority"], "deadline": prac_deadline},
                            reason="Active problem solving improves exam readiness",
                            requires_confirmation=True,
                            status="planned",
                            depends_on=["step_02"] if len(steps) >= 2 else ["step_01"],
                        )
                    )

            summary = f"Preparation roadmap for {subject} exam on {exam_date} ({len(steps)} steps planned)."
            return GoalPlan(
                goal=f"Prepare for {subject} Exam",
                summary=summary,
                source_tool_ids=sources,
                steps=steps,
                confidence=1.0,
            )

        # No upcoming exam found (verified empty from successful read)
        return GoalPlan(
            goal="Prepare for Exams",
            summary="You don't have any upcoming exams scheduled in DayMentor.",
            source_tool_ids=sources,
            steps=[
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title="No Upcoming Exams",
                    description="No exams scheduled. You can focus on regular daily tasks or explore new subjects.",
                    step_type="read_summary",
                    status="completed",
                )
            ],
            confidence=1.0,
        )

    def _plan_cricket_goal(self, cleaned_prompt: str) -> GoalPlan:
        """Construct rematch or new match creation plan."""
        if not self.client.is_authenticated:
            return GoalPlan(
                goal="Set up Cricket Match",
                summary="Sign in to your Aachman Account to manage cricket match plans.",
                source_tool_ids=[],
                steps=[],
                confidence=0.0,
            )

        res_match = self.read_executor.execute_read_intent(
            JarvisReadIntent(tool_id="read.cricket.last_match", confidence=1.0)
        )
        sources = ["read.cricket.last_match"]

        if "rematch" in cleaned_prompt and res_match.status == "success" and res_match.data.get("has_match"):
            m = res_match.data.get("match", {})
            team_a = m.get("team_a") or m.get("teamA") or "Team A"
            team_b = m.get("team_b") or m.get("teamB") or "Team B"
            m_type = m.get("match_type") or m.get("matchType") or "T20"
            overs = int(m.get("overs") or (20 if m_type == "T20" else 50))

            steps = [
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title="Review Previous Match",
                    description=f"Last match was {team_a} vs {team_b} ({m_type}).",
                    step_type="read_summary",
                    status="completed",
                ),
                GoalPlanStep(
                    step_id="step_02",
                    order=2,
                    title=f"Create Rematch: {team_a} vs {team_b}",
                    description=f"{m_type} match with {overs} overs.",
                    step_type="write_action",
                    command_id="action.cricket.create_match",
                    parameters={"team_a": team_a, "team_b": team_b, "match_type": m_type, "overs": overs},
                    reason=f"Rematch between {team_a} and {team_b}",
                    requires_confirmation=True,
                    status="ready",
                    depends_on=["step_01"],
                ),
            ]
            return GoalPlan(
                goal=f"Rematch: {team_a} vs {team_b}",
                summary=f"Set up a rematch of the latest match between {team_a} and {team_b}.",
                source_tool_ids=sources,
                steps=steps,
                confidence=1.0,
            )

        # General match request without known teams -> Input Needed step
        return GoalPlan(
            goal="Set up Weekend Cricket Match",
            summary="Please specify Team A and Team B to schedule a new Cricket Scorer match.",
            source_tool_ids=sources,
            steps=[
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title="Provide Team Names",
                    description="Enter Team A and Team B names to configure the match fixture.",
                    step_type="suggestion",
                    command_id=None,
                    parameters={},
                    reason="Both Team A and Team B names are required to create a match.",
                    requires_confirmation=False,
                    status="ready",
                )
            ],
            confidence=0.9,
        )


    def _plan_hackathon_goal(self) -> GoalPlan:
        """Construct hackathon simulation practice plan."""
        if not self.client.is_authenticated:
            return GoalPlan(
                goal="Hackathon Simulation Practice",
                summary="Sign in to your Aachman Account to manage hackathon practice runs.",
                source_tool_ids=[],
                steps=[],
                confidence=0.0,
            )

        res_latest = self.read_executor.execute_read_intent(
            JarvisReadIntent(tool_id="read.hackathon.latest_result", confidence=1.0)
        )
        sources = ["read.hackathon.latest_result"]

        diff = "medium"
        prob_id = "prob-learnflow"
        prob_title = "LearnFlow AI"

        if res_latest.status == "success" and res_latest.data.get("has_result"):
            res = res_latest.data.get("result", {})
            score = res.get("final_score") or res.get("score") or 0
            if score >= 80:
                diff = "hard"
                prob_id = "prob-codequest"
                prob_title = "CodeQuest RPG"
            elif score <= 50:
                diff = "easy"
                prob_id = "prob-quizwiz"
                prob_title = "QuizWiz Games"

        steps = [
            GoalPlanStep(
                step_id="step_01",
                order=1,
                title="Evaluate Past Performance",
                description=f"Assessed previous hackathon result. Recommending {diff.capitalize()} challenge: {prob_title}.",
                step_type="read_summary",
                status="completed",
            ),
            GoalPlanStep(
                step_id="step_02",
                order=2,
                title=f"Start Challenge: {prob_title}",
                description=f"Launch hackathon simulation on {diff.capitalize()} difficulty.",
                step_type="write_action",
                command_id="action.hackathon.start_simulation",
                parameters={"problem_id": prob_id, "problem_title": prob_title, "difficulty": diff},
                reason=f"Challenges problem solving at {diff} level",
                requires_confirmation=True,
                status="ready",
                depends_on=["step_01"],
            ),
        ]

        return GoalPlan(
            goal="Hackathon Simulation Practice",
            summary=f"Practice plan with progressive {diff} challenge ({len(steps)} steps).",
            source_tool_ids=sources,
            steps=steps,
            confidence=1.0,
        )

    # ── Step Execution & Coordination ─────────────────────────────────────────

    def execute_plan_step(
        self,
        plan: GoalPlan,
        step_id: str,
        confirm: bool = False,
        edited_parameters: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute or confirm a specific step in the plan with centralized guards."""
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if not step:
            return ExecutionResult(
                command_id="unknown",
                status="failed",
                message=f"Step '{step_id}' not found in plan.",
            )

        # ── 1. Terminal / Non-Executable State Enforcement ────────────────────
        if step.status == "completed":
            return ExecutionResult(
                command_id=step.command_id or "read_summary",
                status="success",
                message=f"Step '{step.title}' has already been completed.",
                preview_data=step.result or {},
            )

        if step.status == "skipped":
            return ExecutionResult(
                command_id=step.command_id or "unknown",
                status="rejected",
                message=f"Cannot execute '{step.title}': Step was skipped.",
            )

        if step.status == "cancelled":
            return ExecutionResult(
                command_id=step.command_id or "unknown",
                status="rejected",
                message=f"Cannot execute '{step.title}': Step was cancelled.",
            )

        if step.status == "recovery_rejected":
            return ExecutionResult(
                command_id=step.command_id or "unknown",
                status="rejected",
                message=f"Cannot execute '{step.title}': Step is in recovery_rejected state. Safe recovery was refused.",
            )

        # Check dependencies
        for dep_id in step.depends_on:
            dep_step = next((s for s in plan.steps if s.step_id == dep_id), None)
            if dep_step and dep_step.status not in ("completed", "skipped"):
                step.status = "blocked"
                return ExecutionResult(
                    command_id=step.command_id or "unknown",
                    status="rejected",
                    message=f"Cannot execute '{step.title}': Dependent step '{dep_step.title}' is not completed.",
                )

        # Handle Read Summary
        if step.step_type == "read_summary":
            step.status = "completed"
            return ExecutionResult(
                command_id="read_summary",
                status="success",
                message=f"Reviewed: {step.title}",
            )

        # ── 2. Handle Write Action ────────────────────────────────────────────
        if step.step_type == "write_action":
            command_id = step.command_id or "unknown"
            if command_id not in JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS:
                step.status = "failed"
                return ExecutionResult(
                    command_id=command_id,
                    status="rejected",
                    message=f"Command ID '{command_id}' is not authorized.",
                )

            # Apply and validate edits for fresh steps
            if edited_parameters is not None:
                if step.status == "recovery_pending":
                    return ExecutionResult(
                        command_id=command_id,
                        status="rejected",
                        message="Recovery payload must be immutable. Create a new plan to modify parameters.",
                    )
                # Validate edited parameters without corrupting the existing step
                candidate_params = dict(step.parameters)
                candidate_params.update(edited_parameters)
                val_err = validate_action_parameters(command_id, candidate_params)
                if val_err:
                    return ExecutionResult(
                        command_id=command_id,
                        status="rejected",
                        message=f"Invalid edited parameters: {val_err}",
                    )
                step.parameters = candidate_params

            # ── 3. Mandatory Explicit Confirmation for ALL Writes ─────────────
            if not confirm:
                if step.status == "recovery_pending":
                    msg = f"Retry interrupted action requires explicit confirmation: {step.title}"
                else:
                    msg = f"Confirmation required to execute: {step.title}"
                return ExecutionResult(
                    command_id=command_id,
                    status="preview",
                    message=msg,
                    requires_confirmation=True,
                    preview_data=step.parameters,
                )

            # ── 4. Immediate Pre-Dispatch Ownership Check ─────────────────────
            if plan.owner_id:
                if not self.client.is_authenticated or self.client.user_id != plan.owner_id:
                    log.warning(
                        "Pre-dispatch ownership rejection: client=%s, plan.owner=%s",
                        self.client.user_id if self.client.is_authenticated else "unauthenticated",
                        plan.owner_id,
                    )
                    return ExecutionResult(
                        command_id=command_id,
                        status="rejected",
                        message="User authentication or ownership mismatch. Execution rejected.",
                    )

            # Validate parameters before coordination
            param_err = validate_action_parameters(command_id, step.parameters)
            if param_err:
                step.status = "failed"
                return ExecutionResult(
                    command_id=command_id,
                    status="rejected",
                    message=f"Pre-dispatch parameter validation failed: {param_err}",
                )

            # ── 5. Multi-Session Coordination under PlanLock ──────────────────
            try:
                with self.plan_store.get_plan_lock(plan.plan_id):
                    # Reload authoritative state from disk while coordinated
                    auth_owner = self.client.user_id if self.client.is_authenticated else None
                    reloaded_raw = self.plan_store.load_plan(plan.plan_id, owner_id=auth_owner)
                    if reloaded_raw:
                        reloaded_step = next(
                            (s for s in reloaded_raw.get("steps", []) if s.get("step_id") == step_id),
                            None,
                        )
                        if reloaded_step:
                            # If another session already assigned a key or completed it
                            if reloaded_step.get("status") == "completed":
                                step.status = "completed"
                                step.result = reloaded_step.get("result")
                                return ExecutionResult(
                                    command_id=command_id,
                                    status="success",
                                    message=f"Step '{step.title}' was already completed by another session.",
                                    preview_data=step.result or {},
                                )
                            if reloaded_step.get("status") == "recovery_rejected":
                                step.status = "recovery_rejected"
                                step.error_message = reloaded_step.get("error_message")
                                return ExecutionResult(
                                    command_id=command_id,
                                    status="rejected",
                                    message=step.error_message or "Step was rejected during recovery.",
                                )

                            if reloaded_step.get("idempotency_key"):
                                step.idempotency_key = reloaded_step["idempotency_key"]
                            if reloaded_step.get("confirmation_fingerprint"):
                                step.confirmation_fingerprint = reloaded_step["confirmation_fingerprint"]

                    # Differentiated recovery vs fresh confirmation handling
                    if step.status == "recovery_pending":
                        if not step.idempotency_key:
                            step.status = "recovery_rejected"
                            step.error_message = "Unsafe recovery: missing idempotency key."
                            self.plan_store.save_plan(plan.to_dict())
                            return ExecutionResult(
                                command_id=command_id,
                                status="rejected",
                                message="Recovery refused: missing idempotency key.",
                            )
                        if step.confirmation_fingerprint:
                            expected_fp = compute_confirmation_fingerprint(
                                plan_id=plan.plan_id,
                                step_id=step.step_id,
                                command_id=command_id,
                                parameters=step.parameters,
                            )
                            if expected_fp != step.confirmation_fingerprint:
                                step.status = "recovery_rejected"
                                step.error_message = "Unsafe recovery: confirmation fingerprint mismatch."
                                self.plan_store.save_plan(plan.to_dict())
                                return ExecutionResult(
                                    command_id=command_id,
                                    status="rejected",
                                    message="Recovery refused: payload changed after confirmation.",
                                )
                    else:
                        # Fresh confirmation path: assign key and fingerprint
                        if not step.idempotency_key:
                            step.idempotency_key = str(uuid.uuid4())
                        step.confirmation_fingerprint = compute_confirmation_fingerprint(
                            plan_id=plan.plan_id,
                            step_id=step.step_id,
                            command_id=command_id,
                            parameters=step.parameters,
                        )

                    step.status = "executing"

                    # Persist atomically before releasing lock and before network dispatch
                    self.plan_store.save_plan(plan.to_dict())

            except PlanLockTimeoutError as e:
                log.warning("Plan lock timeout: %s", e)
                return ExecutionResult(
                    command_id=command_id,
                    status="failed",
                    message="This plan is currently being updated by another PyFlare session. Try again.",
                )
            except Exception as e:
                # Pre-dispatch persistence failure: ABORT immediately (0 dispatches)
                log.error("Pre-dispatch persistence failure for plan %s: %s", plan.plan_id, e)
                step.status = "ready"
                return ExecutionResult(
                    command_id=command_id,
                    status="failed",
                    message=f"Pre-dispatch save failed. Execution aborted to protect idempotency: {e}",
                )

            # ── 6. Dispatch via Executor (Lock is released) ───────────────────
            intent = JarvisEcosystemIntent(
                command_id=command_id,
                confidence=1.0,
                parameters=step.parameters,
                requires_confirmation=False,
                summary=step.title,
                idempotency_key=step.idempotency_key,
            )

            res = self.executor.execute_intent(intent, confirm=True)

            # ── 7. Post-Dispatch Result Persistence under Lock ────────────────
            try:
                with self.plan_store.get_plan_lock(plan.plan_id):
                    if res.status == "success":
                        step.status = "completed"
                        step.result = res.preview_data or {"message": res.message, "deep_link": res.deep_link}
                        for next_step in plan.steps:
                            if step.step_id in next_step.depends_on and next_step.status == "planned":
                                next_step.status = "ready"
                    else:
                        step.status = "failed"
                        step.error_message = res.message

                    self.plan_store.save_plan(plan.to_dict())
            except Exception as e:
                log.warning("Could not persist post-dispatch result for plan %s: %s", plan.plan_id, e)

            return res

        return ExecutionResult(command_id="unknown", status="failed", message="Unknown step type.")

    def skip_plan_step(self, plan: GoalPlan, step_id: str) -> bool:
        """Mark a plan step as skipped without performing any writes."""
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if not step or step.status == "completed":
            return False

        step.status = "skipped"
        # Unblock dependent steps so user can proceed
        for next_step in plan.steps:
            if step.step_id in next_step.depends_on and next_step.status == "planned":
                next_step.status = "ready"

        try:
            with self.plan_store.get_plan_lock(plan.plan_id):
                self.plan_store.save_plan(plan.to_dict())
        except Exception as e:
            log.warning("Could not auto-persist plan %s: %s", plan.plan_id, e)
        return True

    def cancel_plan(self, plan: GoalPlan) -> None:
        """Cancel all remaining unexecuted steps in the plan."""
        for step in plan.steps:
            if step.status not in ("completed", "skipped"):
                step.status = "cancelled"

        try:
            with self.plan_store.get_plan_lock(plan.plan_id):
                self.plan_store.save_plan(plan.to_dict())
        except Exception as e:
            log.warning("Could not auto-persist plan %s: %s", plan.plan_id, e)

    def load_active_plans(self) -> List[GoalPlan]:
        """Load all unfinished active plans belonging to the current user (fail-closed)."""
        if not self.client.is_authenticated or not self.client.user_id:
            return []
        raw_plans = self.plan_store.load_active_plans(owner_id=self.client.user_id)
        return [GoalPlan.from_dict(p) for p in raw_plans]

    def resume_plan(self, plan_id: str) -> Optional[GoalPlan]:
        """Load and reconstruct a specific plan by ID for the current user (fail-closed)."""
        if not self.client.is_authenticated or not self.client.user_id:
            return None
        raw = self.plan_store.load_plan(plan_id, owner_id=self.client.user_id)
        if not raw:
            return None
        return GoalPlan.from_dict(raw)
