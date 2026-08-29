"""Jarvis Cross-App Read + Action Planner v1.

Synthesizes trusted read intelligence with contextual write action suggestions:
- Exam revision task planning with duplicate detection and urgency calculation
- Cricket rematch setup from previous match history
- Hackathon challenge progression based on completed score
- Zero side-effects prior to explicit user confirmation
- Strict allowlists for both source read tools and target action command IDs
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .client import AachmanEcosystemClient, get_ecosystem_client
from .constants import (
    HACKATHON_PROBLEMS,
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
    JARVIS_ALLOWED_READ_TOOL_IDS,
)
from .read_executor import EcosystemReadExecutor, JarvisReadResponse
from .read_interpreter import (
    JarvisReadIntent,
    get_current_date_kolkata,
    interpret_ecosystem_read_query,
)
from ..logging_setup import get_logger

log = get_logger("ecosystem.planner")


@dataclass
class SuggestedAction:
    """Structured, typed action recommendation produced by the planner."""
    command_id: str
    title: str
    reason: str
    parameters: Dict[str, Any]
    confidence: float
    source_tool_ids: List[str] = field(default_factory=list)
    requires_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "title": self.title,
            "reason": self.reason,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "source_tool_ids": self.source_tool_ids,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class PlannerResult:
    """Combined output containing natural response and optional action suggestion."""
    answer_text: str
    suggested_action: Optional[SuggestedAction] = None
    source_reads: List[JarvisReadResponse] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_text": self.answer_text,
            "suggested_action": self.suggested_action.to_dict() if self.suggested_action else None,
            "source_reads": [r.to_dict() for r in self.source_reads],
        }


def _normalize_subject(text: str) -> str:
    """Normalize subject or title for duplicate comparison."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\b(exam|revision|review|test|preparation|study|homework|practice)\b", "", t)
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _is_duplicate_task(suggested_title: str, existing_tasks: List[Dict[str, Any]]) -> bool:
    """Determine if a task covering the same subject already exists."""
    norm_sugg = _normalize_subject(suggested_title)
    if not norm_sugg:
        return False

    for task in existing_tasks:
        norm_exist = _normalize_subject(task.get("title", ""))
        if not norm_exist:
            continue
        # Direct equality or substring containment
        if norm_sugg == norm_exist or norm_sugg in norm_exist or norm_exist in norm_sugg:
            return True
    return False


class EcosystemPlanner:
    """Synthesizes read facts into proactive, contextual action suggestions."""

    def __init__(
        self,
        client: Optional[AachmanEcosystemClient] = None,
        read_executor: Optional[EcosystemReadExecutor] = None,
    ):
        self.read_executor = read_executor or EcosystemReadExecutor(client)
        self.client = client or (self.read_executor.client if self.read_executor else get_ecosystem_client())

    def plan_from_prompt(
        self, prompt: str, now: Optional[datetime.datetime] = None
    ) -> Optional[PlannerResult]:
        """Analyze prompt, perform necessary reads, and generate contextual recommendations."""
        if not prompt or not isinstance(prompt, str):
            return None

        cleaned = prompt.strip().lower()

        # Reject prompt injection or arbitrary SQL attempts
        if any(p in cleaned for p in ("select * from", "insert into", "delete from", "drop table", "ignore rules")):
            return None

        # ── 1. Cricket Rematch Planning ──
        if re.search(r"\b(rematch|play again|run match again)\b", cleaned):
            return self._plan_cricket_rematch()

        # ── 2. Hackathon Practice / Next Challenge Planning ──
        if (
            re.search(r"\b(another|next|practice|more)\s+hackathon\s+(challenge|simulation|problem)\b", cleaned)
            or re.search(r"\bgive me (a|another) hackathon\b", cleaned)
        ):
            return self._plan_hackathon_challenge()

        # ── 3. Study / Exam Revision Planning ──
        if (
            re.search(r"\bwhat (should|do) i (need to )?study\b", cleaned)
            or re.search(r"\b(study|revision)\s+plan\b", cleaned)
            or re.search(r"\bwhat to study\b", cleaned)
        ):
            return self._plan_study_revision(now)

        # ── 4. Standard Read-Only Fallback ──
        read_intent = interpret_ecosystem_read_query(prompt, now=now)
        if read_intent is not None:
            read_res = self.read_executor.execute_read_intent(read_intent)
            # If user asked about upcoming exams, also check for proactive revision suggestion
            if read_intent.tool_id == "read.daymentor.next_exam" and read_res.status == "success":
                plan = self._synthesize_exam_action(read_res, now)
                if plan:
                    return PlannerResult(
                        answer_text=read_res.human_text,
                        suggested_action=plan,
                        source_reads=[read_res],
                    )
            return PlannerResult(
                answer_text=read_res.human_text,
                suggested_action=None,
                source_reads=[read_res],
            )

        return None

    def _plan_study_revision(self, now: Optional[datetime.datetime] = None) -> PlannerResult:
        """Evaluate upcoming exams and current tasks to recommend revision."""
        if not self.client.is_authenticated:
            return PlannerResult(
                answer_text="Sign in to your Aachman Account to receive personalized study recommendations.",
                suggested_action=None,
            )

        # Read upcoming exams and current tasks
        intent_exam = JarvisReadIntent(tool_id="read.daymentor.next_exam", confidence=1.0)
        res_exam = self.read_executor.execute_read_intent(intent_exam)

        ref_dt = get_current_date_kolkata(now)
        today_str = ref_dt.strftime("%Y-%m-%d")
        intent_tasks = JarvisReadIntent(
            tool_id="read.daymentor.tasks_today",
            confidence=1.0,
            parameters={"target_date": today_str},
        )
        res_tasks = self.read_executor.execute_read_intent(intent_tasks)

        sources = [res_exam, res_tasks]

        if res_exam.status == "success" and res_exam.data.get("has_exam"):
            exam = res_exam.data.get("exam", {})
            days_rem = res_exam.data.get("days_remaining", 999)
            subject = exam.get("subjectName") or exam.get("subjectId") or "Upcoming Exam"

            existing_tasks = res_tasks.data.get("tasks", [])
            suggested_title = f"{subject} revision"

            # Duplicate check
            if _is_duplicate_task(suggested_title, existing_tasks):
                text = (
                    f"{res_exam.human_text}\n"
                    f"You already have a {subject} study task scheduled for today."
                )
                return PlannerResult(answer_text=text, suggested_action=None, source_reads=sources)

            # Deadline & Urgency logic
            if days_rem <= 1:
                deadline = today_str
                priority = "high"
            elif days_rem <= 3:
                deadline = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                priority = "high"
            else:
                deadline = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                priority = "medium"

            reason = f"Your {subject} exam is in {days_rem} days and you do not have a revision task scheduled."
            action = SuggestedAction(
                command_id="action.daymentor.create_task",
                title=f"Create DayMentor Task: {suggested_title}",
                reason=reason,
                parameters={
                    "title": suggested_title,
                    "priority": priority,
                    "deadline": deadline,
                },
                confidence=1.0,
                source_tool_ids=["read.daymentor.next_exam", "read.daymentor.tasks_today"],
                requires_confirmation=True,
            )

            text = f"{res_exam.human_text}\n\nSuggested Next Step:\nCreate a {priority}-priority revision task for {deadline}."
            return PlannerResult(answer_text=text, suggested_action=action, source_reads=sources)

        # No upcoming exam
        text = "You don't have any upcoming exams scheduled. You can focus on your regular daily tasks or explore new topics."
        return PlannerResult(answer_text=text, suggested_action=None, source_reads=sources)

    def _synthesize_exam_action(
        self, res_exam: JarvisReadResponse, now: Optional[datetime.datetime] = None
    ) -> Optional[SuggestedAction]:
        """Helper to attach an action when user specifically asks 'when is my next exam?'."""
        exam = res_exam.data.get("exam")
        days_rem = res_exam.data.get("days_remaining", 999)
        if not exam or days_rem > 7:
            return None

        subject = exam.get("subjectName") or exam.get("subjectId") or "Exam"
        ref_dt = get_current_date_kolkata(now)
        deadline = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        priority = "high" if days_rem <= 3 else "medium"

        return SuggestedAction(
            command_id="action.daymentor.create_task",
            title=f"Create DayMentor Task: {subject} revision",
            reason=f"Your {subject} exam is in {days_rem} days.",
            parameters={
                "title": f"{subject} revision",
                "priority": priority,
                "deadline": deadline,
            },
            confidence=0.9,
            source_tool_ids=["read.daymentor.next_exam"],
            requires_confirmation=True,
        )

    def _plan_cricket_rematch(self) -> PlannerResult:
        """Plan a rematch based on the user's latest cricket match."""
        if not self.client.is_authenticated:
            return PlannerResult(
                answer_text="Sign in to your Aachman Account to set up a rematch from your match history.",
                suggested_action=None,
            )

        intent_match = JarvisReadIntent(tool_id="read.cricket.last_match", confidence=1.0)
        res_match = self.read_executor.execute_read_intent(intent_match)

        if res_match.status == "success" and res_match.data.get("has_match"):
            match = res_match.data.get("match", {})
            team_a = match.get("team_a", "Team A")
            team_b = match.get("team_b", "Team B")
            m_type = match.get("match_type", "T20")
            overs = 20 if m_type == "T20" else (50 if m_type == "ODI" else 20)

            reason = f"Setting up a rematch between {team_a} and {team_b} ({m_type})."
            action = SuggestedAction(
                command_id="action.cricket.create_match",
                title=f"Create Cricket Match: {team_a} vs {team_b} ({m_type})",
                reason=reason,
                parameters={
                    "team_a": team_a,
                    "team_b": team_b,
                    "match_type": m_type,
                    "overs": overs,
                },
                confidence=1.0,
                source_tool_ids=["read.cricket.last_match"],
                requires_confirmation=True,
            )

            text = f"{res_match.human_text}\n\nSuggested Next Step:\nSet up a rematch between {team_a} and {team_b}."
            return PlannerResult(answer_text=text, suggested_action=action, source_reads=[res_match])

        return PlannerResult(
            answer_text="You don't have a previous cricket match recorded to rematch. You can start a new match anytime.",
            suggested_action=None,
            source_reads=[res_match],
        )

    def _plan_hackathon_challenge(self) -> PlannerResult:
        """Plan next hackathon challenge based on prior performance."""
        if not self.client.is_authenticated:
            return PlannerResult(
                answer_text="Sign in to your Aachman Account to track challenge simulations.",
                suggested_action=None,
            )

        intent_res = JarvisReadIntent(tool_id="read.hackathon.latest_result", confidence=1.0)
        res_hack = self.read_executor.execute_read_intent(intent_res)

        target_diff = "medium"
        reason = "Ready for a new product strategy simulation challenge."

        if res_hack.status == "success" and res_hack.data.get("has_result"):
            score = res_hack.data.get("result", {}).get("score", 70)
            if score >= 85:
                target_diff = "hard"
                reason = f"You scored {score}/100 in your last challenge. Ready to step up to Hard difficulty!"
            elif score < 60:
                target_diff = "easy"
                reason = "Let's build momentum with an accessible challenge."

        # Pick default problem
        problem = HACKATHON_PROBLEMS[0]
        prob_id = problem["id"]
        prob_title = problem["title"]

        action = SuggestedAction(
            command_id="action.hackathon.start_simulation",
            title=f"Start Hackathon Simulation: {prob_title} ({target_diff})",
            reason=reason,
            parameters={
                "problem_id": prob_id,
                "problem_title": prob_title,
                "difficulty": target_diff,
            },
            confidence=1.0,
            source_tool_ids=["read.hackathon.latest_result"],
            requires_confirmation=True,
        )

        intro = res_hack.human_text if res_hack.status == "success" else "Here is your next recommended simulation:"
        text = f"{intro}\n\nSuggested Next Step:\nStart '{prob_title}' on {target_diff.capitalize()} difficulty."
        return PlannerResult(answer_text=text, suggested_action=action, source_reads=[res_hack])
