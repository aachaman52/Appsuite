"""Deterministic Natural Language Command Interpreter for PyFlare Jarvis."""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .constants import JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS, HACKATHON_PROBLEMS


@dataclass
class JarvisEcosystemIntent:
    command_id: str
    confidence: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = True
    summary: str = ""
    missing_fields: List[str] = field(default_factory=list)
    idempotency_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "confidence": self.confidence,
            "parameters": self.parameters,
            "requires_confirmation": self.requires_confirmation,
            "summary": self.summary,
            "missing_fields": self.missing_fields,
            "idempotency_key": self.idempotency_key,
        }


def format_local_date(dt: datetime.datetime) -> str:
    """Format datetime as YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def parse_relative_date(text: str) -> Tuple[Optional[str], str]:
    """Parse relative dates such as 'today', 'tomorrow', 'next monday'."""
    lower = text.lower()
    now = datetime.datetime.now()

    # "today" / "tonight" / "this evening"
    if re.search(r"\b(today|tonight|this evening)\b", lower):
        cleaned = re.sub(r"\b(today|tonight|this evening)\b", "", lower).strip()
        return format_local_date(now), cleaned

    # "tomorrow" / "tomorrow morning" / "tomorrow evening"
    if re.search(r"\btomorrow(\s+(morning|evening|night))?\b", lower):
        tom = now + datetime.timedelta(days=1)
        cleaned = re.sub(r"\btomorrow(\s+(morning|evening|night))?\b", "", lower).strip()
        return format_local_date(tom), cleaned

    # Weekdays: "monday", "next friday", etc.
    days_of_week = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_match = re.search(r"\b(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lower)
    if day_match:
        target_day_name = day_match.group(2)
        is_next = bool(day_match.group(1))
        target_idx = days_of_week.index(target_day_name)
        current_idx = now.weekday()
        diff = target_idx - current_idx
        if diff <= 0 or is_next:
            diff += 7
        target_date = now + datetime.timedelta(days=diff)
        cleaned = lower[:day_match.start()] + lower[day_match.end():]
        return format_local_date(target_date), cleaned.strip()

    return None, text


def interpret_ecosystem_query(raw_query: str) -> Optional[JarvisEcosystemIntent]:
    """Interpret natural language into a registered Aachman Ecosystem Command.

    Guarantees:
    - Never generates arbitrary command IDs outside JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS.
    - Rejects prompt injections and malicious execution attempts.
    - Distinguishes navigation (no confirmation) vs writes (requires confirmation).
    """
    if not raw_query or not isinstance(raw_query, str):
        return None

    query = raw_query.strip()
    if not query:
        return None

    lower = query.lower()

    # ── 1. SECURITY & INJECTION FILTER ──
    if any(
        kw in lower
        for kw in [
            "ignore previous",
            "ignore instructions",
            "delete_user",
            "delete database",
            "drop table",
            "admin.delete",
            "action.admin",
            "<script",
            "javascript:",
            "exec(",
            "eval(",
            "system(",
            "subprocess",
        ]
    ):
        return None

    # ── 2. APP NAVIGATION COMMANDS (app.open.*) ──
    if (
        re.search(r"\b(open|launch|go to|take me to|switch to)\s+(daymentor|study|planner)\b", lower)
        or lower == "daymentor"
    ):
        return JarvisEcosystemIntent(
            command_id="app.open.daymentor",
            confidence=0.95,
            parameters={},
            requires_confirmation=False,
            summary="Open DayMentor Planner",
        )

    if (
        re.search(r"\b(open|launch|go to|take me to|switch to)\s+(cricket|cricket scorer|scorecard)\b", lower)
        or lower in ("cricket", "cricket scorer")
    ):
        return JarvisEcosystemIntent(
            command_id="app.open.cricket_scorer",
            confidence=0.95,
            parameters={},
            requires_confirmation=False,
            summary="Open Cricket Scorer",
        )

    if (
        re.search(r"\b(open|launch|go to|take me to|switch to)\s+(hackathon|the hackathon simulator|simulator)\b", lower)
        or lower in ("hackathon", "hackathon simulator")
    ):
        return JarvisEcosystemIntent(
            command_id="app.open.hackathon_simulator",
            confidence=0.95,
            parameters={},
            requires_confirmation=False,
            summary="Open The Hackathon Simulator",
        )

    if (
        re.search(r"\b(open|launch|go to|take me to|switch to)\s+(hub|aachman hub|home|portal)\b", lower)
        or lower in ("hub", "aachman hub")
    ):
        return JarvisEcosystemIntent(
            command_id="app.open.aachman_hub",
            confidence=0.95,
            parameters={},
            requires_confirmation=False,
            summary="Open Aachman Hub Portal",
        )

    # ── 3. CRICKET SCORER MATCH ACTION (action.cricket.create_match) ──
    if any(k in lower for k in ["cricket", "match", " vs ", " v ", "overs"]):
        match_type = "T20"
        overs = 20

        if re.search(r"\b(t20|twenty20)\b", lower):
            match_type = "T20"
            overs = 20
        elif re.search(r"\b(odi|one day)\b", lower):
            match_type = "ODI"
            overs = 50
        elif re.search(r"\b(test|test match)\b", lower):
            match_type = "Test"
            overs = 90

        overs_match = re.search(r"\b(\d+)\s*(overs|ov|o)\b", lower)
        if overs_match:
            try:
                parsed_ov = int(overs_match.group(1))
                if 1 <= parsed_ov <= 100:
                    overs = parsed_ov
            except ValueError:
                pass

        vs_match = re.search(
            r"(?:match\s+|game\s+)?([A-Za-z0-9\s]{2,25})\s+(?:vs\.?|v\.?)\s+([A-Za-z0-9\s]{2,25})",
            query,
            re.IGNORECASE,
        )

        team_a = ""
        team_b = ""
        missing: List[str] = []

        if vs_match:
            team_a = re.sub(
                r"\b(new|create|start|a|t20|twenty20|odi|test|cricket|match|game)\b",
                "",
                vs_match.group(1),
                flags=re.IGNORECASE,
            ).strip()
            team_b = re.sub(
                r"\b(\d+\s*overs?|\d+\s*ov|t20|odi|test|match|game)\b",
                "",
                vs_match.group(2),
                flags=re.IGNORECASE,
            ).strip()
            if team_a:
                team_a = team_a[0].upper() + team_a[1:]
            if team_b:
                team_b = team_b[0].upper() + team_b[1:]

        if not team_a:
            missing.append("team_a")
        if not team_b:
            missing.append("team_b")

        if (
            lower.startswith("new match")
            or lower.startswith("create match")
            or lower.startswith("create cricket")
            or lower.startswith("start match")
            or lower.startswith("new t20")
            or (team_a and team_b)
        ):
            title_summary = f"{team_a} vs {team_b} ({match_type})" if team_a and team_b else f"New {match_type} Match"
            return JarvisEcosystemIntent(
                command_id="action.cricket.create_match",
                confidence=0.92 if team_a and team_b else 0.75,
                parameters={
                    "team_a": team_a,
                    "team_b": team_b,
                    "match_type": match_type,
                    "overs": overs,
                },
                requires_confirmation=True,
                summary=f"Create Cricket Match: {title_summary}",
                missing_fields=missing,
            )

    # ── 4. HACKATHON SIMULATION ACTION (action.hackathon.start_simulation) ──
    if any(k in lower for k in ["hackathon", "simulation", "challenge run"]):
        difficulty = "medium"
        if re.search(r"\b(easy|beginner|10 min)\b", lower):
            difficulty = "easy"
        elif re.search(r"\b(hard|expert|advanced|5 min)\b", lower):
            difficulty = "hard"
        elif re.search(r"\b(medium|normal|7 min)\b", lower):
            difficulty = "medium"

        problem_id = "prob-learnflow"
        problem_title = "LearnFlow AI (Adaptive Study Planner)"

        if "quiz" in lower or "game" in lower:
            problem_id = "prob-quizwiz"
            problem_title = "QuizWiz Games (Gamified Algorithm Learning)"
        elif "note" in lower or "scribe" in lower:
            problem_id = "prob-eduscribe"
            problem_title = "EduScribe Assistant (Audio Note Transcriber)"
        elif "rpg" in lower or "maze" in lower or "code" in lower:
            problem_id = "prob-codequest"
            problem_title = "CodeQuest RPG (Coding Maze RPG)"
        elif "health" in lower or "sync" in lower or "vital" in lower:
            problem_id = "prob-vitalsync"
            problem_title = "VitalSync Health (Real-time Metric Tracker)"

        if (
            lower.startswith("start")
            or lower.startswith("launch")
            or lower.startswith("new")
            or lower.startswith("play")
            or "challenge" in lower
            or "hackathon" in lower
        ):
            return JarvisEcosystemIntent(
                command_id="action.hackathon.start_simulation",
                confidence=0.9,
                parameters={
                    "problem_id": problem_id,
                    "problem_title": problem_title,
                    "difficulty": difficulty,
                },
                requires_confirmation=True,
                summary=f"Start Hackathon Simulation: {problem_title} ({difficulty})",
                missing_fields=[],
            )

    # ── 5. DAYMENTOR TASK ACTION (action.daymentor.create_task) ──
    is_task_prefix = (
        lower.startswith("add ")
        or lower.startswith("create ")
        or lower.startswith("remind me ")
        or lower.startswith("new task")
        or lower.startswith("todo ")
        or "revision" in lower
        or "homework" in lower
        or "study task" in lower
        or "assignment" in lower
    )

    if is_task_prefix:
        date_str, cleaned = parse_relative_date(query)

        title = re.sub(
            r"^(add|create|remind me to|remind me|new task|todo|schedule|plan)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"^(a|an|the)\s+", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+(task|reminder|todo)$", "", title, flags=re.IGNORECASE).strip()

        if title:
            title = title[0].upper() + title[1:]

        priority = "medium"
        if re.search(r"\b(urgent|high priority|asap|important)\b", query, re.IGNORECASE):
            priority = "high"
            title = re.sub(r"\b(urgent|high priority|asap|important)\b", "", title, flags=re.IGNORECASE).strip()
        elif re.search(r"\b(low priority|casual)\b", query, re.IGNORECASE):
            priority = "low"
            title = re.sub(r"\b(low priority|casual)\b", "", title, flags=re.IGNORECASE).strip()

        missing = []
        if not title:
            missing.append("title")

        if len(title) >= 2 or is_task_prefix:
            final_title = title or "Study Session"
            due_text = f" (Due {date_str})" if date_str else ""
            return JarvisEcosystemIntent(
                command_id="action.daymentor.create_task",
                confidence=0.92 if title else 0.7,
                parameters={
                    "title": final_title,
                    "priority": priority,
                    "deadline": date_str,
                },
                requires_confirmation=True,
                summary=f"Create DayMentor Task: {final_title}{due_text}",
                missing_fields=missing,
            )

    return None
