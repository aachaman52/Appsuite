"""Jarvis Multi-Step Goal Planner v1.

Decomposes high-level user goals into structured sequences of safe ecosystem steps:
- Grounded in live read facts from canonical read tools
- Step types: read_summary, suggestion, write_action
- Strict per-step review, confirmation, editing, and skipping
- Unique per-step idempotency key assigned only on user confirmation
- Zero planning side-effects prior to explicit confirmation
"""
from __future__ import annotations

import datetime
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import AachmanEcosystemClient, get_ecosystem_client
from .constants import (
    HACKATHON_PROBLEMS,
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
    JARVIS_ALLOWED_READ_TOOL_IDS,
)
from .executor import EcosystemExecutor, ExecutionResult
from .interpreter import JarvisEcosystemIntent
from .planner import _is_duplicate_task, _normalize_subject
from .read_executor import EcosystemReadExecutor, JarvisReadResponse
from .read_interpreter import (
    JarvisReadIntent,
    get_current_date_kolkata,
    interpret_ecosystem_read_query,
)
from .plan_store import PlanStore, CURRENT_SCHEMA_VERSION, get_current_timestamp_iso
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
    status: str = "planned"  # "planned" | "ready" | "confirmed" | "executing" | "completed" | "skipped" | "cancelled" | "failed" | "blocked" | "recovery_pending"
    depends_on: List[str] = field(default_factory=list)
    idempotency_key: Optional[str] = None
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
            "result": self.result,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GoalPlanStep:
        return cls(
            step_id=data.get("step_id", str(uuid.uuid4())[:8]),
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
    confidence: float
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
            except Exception as e:
                log.warning("Could not auto-persist plan %s: %s", res_plan.plan_id, e)

        return res_plan

    # ── Goal Plan Generators ──────────────────────────────────────────────────

    def _plan_exam_preparation(self, now: Optional[datetime.datetime] = None) -> GoalPlan:
        """Construct multi-step study plan for upcoming exams."""
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

        # Read facts
        res_exam = self.read_executor.execute_read_intent(
            JarvisReadIntent(tool_id="read.daymentor.next_exam", confidence=1.0)
        )
        res_tasks = self.read_executor.execute_read_intent(
            JarvisReadIntent(
                tool_id="read.daymentor.tasks_today",
                confidence=1.0,
                parameters={"target_date": today_str},
            )
        )

        sources = ["read.daymentor.next_exam", "read.daymentor.tasks_today"]
        steps: List[GoalPlanStep] = []

        if res_exam.status == "success" and res_exam.data.get("has_exam"):
            exam = res_exam.data.get("exam", {})
            days_rem = res_exam.data.get("days_remaining", 999)
            subject = exam.get("subjectName") or exam.get("subjectId") or "Subject"
            exam_date = exam.get("date", "Upcoming")

            # Step 1: Read Summary
            steps.append(
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title=f"Review {subject} Exam Schedule",
                    description=f"Exam scheduled on {exam_date} ({days_rem} days remaining).",
                    step_type="read_summary",
                    reason="Confirm exam timeline and urgency",
                    requires_confirmation=False,
                    status="completed",
                )
            )

            existing_tasks = res_tasks.data.get("tasks", [])

            # Step 2: Primary Revision Task
            rev_title = f"{subject} revision"
            if not _is_duplicate_task(rev_title, existing_tasks):
                pri = "high" if days_rem <= 2 else "medium"
                deadline = today_str if days_rem <= 1 else tom_str
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
            if days_rem >= 3:
                prac_title = f"{subject} practice questions"
                if not _is_duplicate_task(prac_title, existing_tasks):
                    prac_deadline = (ref_dt + datetime.timedelta(days=min(2, days_rem - 1))).strftime("%Y-%m-%d")
                    steps.append(
                        GoalPlanStep(
                            step_id="step_03",
                            order=len(steps) + 1,
                            title=f"Create {subject} Practice Task",
                            description=f"Solve mock questions and practice problems (due {prac_deadline}).",
                            step_type="write_action",
                            command_id="action.daymentor.create_task",
                            parameters={"title": prac_title, "priority": "medium", "deadline": prac_deadline},
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

        # No upcoming exam found
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
            team_a = m.get("team_a", "Team A")
            team_b = m.get("team_b", "Team B")
            m_type = m.get("match_type", "T20")
            overs = 20 if m_type == "T20" else 50

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
        """Construct multi-step hackathon simulation practice plan."""
        if not self.client.is_authenticated:
            return GoalPlan(
                goal="Hackathon Practice Simulation",
                summary="Sign in to your Aachman Account to create a hackathon practice plan.",
                source_tool_ids=[],
                steps=[],
                confidence=0.0,
            )

        res_hack = self.read_executor.execute_read_intent(
            JarvisReadIntent(tool_id="read.hackathon.latest_result", confidence=1.0)
        )
        sources = ["read.hackathon.latest_result"]

        diff = "medium"
        reason = "Practice product strategy and system design under simulation constraints."
        steps: List[GoalPlanStep] = []

        if res_hack.status == "success" and res_hack.data.get("has_result"):
            prev_result = res_hack.data.get("result", {})
            score = prev_result.get("score", 70)
            p_title = prev_result.get("title") or prev_result.get("problem_title") or "Challenge"

            steps.append(
                GoalPlanStep(
                    step_id="step_01",
                    order=1,
                    title="Review Recent Performance",
                    description=f"Scored {score}/100 on '{p_title}'.",
                    step_type="read_summary",
                    status="completed",
                )
            )

            if score >= 85:
                diff = "hard"
                reason = f"Excellent score of {score}/100. Progressing to Hard challenge."
            elif score < 60:
                diff = "easy"
                reason = "Focusing on fundamentals with an accessible problem statement."

        prob = HACKATHON_PROBLEMS[1] if len(steps) > 0 else HACKATHON_PROBLEMS[0]
        steps.append(
            GoalPlanStep(
                step_id="step_02",
                order=len(steps) + 1,
                title=f"Start Challenge: {prob['title']}",
                description=f"{diff.capitalize()} difficulty simulation run.",
                step_type="write_action",
                command_id="action.hackathon.start_simulation",
                parameters={"problem_id": prob["id"], "problem_title": prob["title"], "difficulty": diff},
                reason=reason,
                requires_confirmation=True,
                status="ready",
                depends_on=["step_01"] if len(steps) >= 1 else [],
            )
        )

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
        """Execute or confirm a specific step in the plan with safe idempotency key handling."""
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if not step:
            return ExecutionResult(
                command_id="unknown",
                status="failed",
                message=f"Step '{step_id}' not found in plan.",
            )

        # If already completed
        if step.status == "completed":
            return ExecutionResult(
                command_id=step.command_id or "read_summary",
                status="success",
                message=f"Step '{step.title}' has already been completed.",
                preview_data=step.result or {},
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

        # Handle Write Action
        if step.step_type == "write_action":
            if step.command_id not in JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS:
                step.status = "failed"
                return ExecutionResult(
                    command_id=step.command_id or "unknown",
                    status="rejected",
                    message=f"Command ID '{step.command_id}' is not authorized.",
                )

            # Apply edits if user modified parameters before confirmation
            if edited_parameters:
                step.parameters.update(edited_parameters)

            if not confirm:
                return ExecutionResult(
                    command_id=step.command_id,
                    status="preview",
                    message=f"Confirmation required to execute: {step.title}",
                    requires_confirmation=True,
                    preview_data=step.parameters,
                )

            # Assign opaque UUID idempotency key strictly upon confirmation
            if not step.idempotency_key:
                step.idempotency_key = str(uuid.uuid4())

            step.status = "executing"
            intent = JarvisEcosystemIntent(
                command_id=step.command_id or "action.unknown",
                confidence=1.0,
                parameters=step.parameters,
                requires_confirmation=False,
                summary=step.title,
                idempotency_key=step.idempotency_key,
            )

            res = self.executor.execute_intent(intent, confirm=True)
            if res.status == "success":
                step.status = "completed"
                step.result = res.preview_data or {"message": res.message, "deep_link": res.deep_link}
                # Unblock next steps if ready
                for next_step in plan.steps:
                    if step.step_id in next_step.depends_on and next_step.status == "planned":
                        next_step.status = "ready"
            else:
                step.status = "failed"
                step.error_message = res.message

            try:
                self.plan_store.save_plan(plan.to_dict())
            except Exception as e:
                log.warning("Could not auto-persist plan %s: %s", plan.plan_id, e)

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
            self.plan_store.save_plan(plan.to_dict())
        except Exception as e:
            log.warning("Could not auto-persist plan %s: %s", plan.plan_id, e)

    def load_active_plans(self) -> List[GoalPlan]:
        """Load all unfinished active plans belonging to the current user."""
        owner_id = self.client.user_id if self.client.is_authenticated else None
        raw_plans = self.plan_store.load_active_plans(owner_id=owner_id)
        return [GoalPlan.from_dict(p) for p in raw_plans]

    def resume_plan(self, plan_id: str) -> Optional[GoalPlan]:
        """Load and reconstruct a specific plan by ID for the current user."""
        owner_id = self.client.user_id if self.client.is_authenticated else None
        raw = self.plan_store.load_plan(plan_id, owner_id=owner_id)
        if not raw:
            return None
        return GoalPlan.from_dict(raw)
