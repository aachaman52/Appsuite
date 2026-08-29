"""Deterministic Read Intent Interpreter for Jarvis Ecosystem Intelligence v1.

Parses natural-language queries into canonical read tool IDs:
- read.daymentor.tasks_today
- read.daymentor.tasks_tomorrow
- read.daymentor.next_exam
- read.daymentor.study_week
- read.cricket.last_match
- read.cricket.match_summary
- read.hackathon.latest_result
- read.ecosystem.recent_activity
- read.ecosystem.summary
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from .constants import JARVIS_ALLOWED_READ_TOOL_IDS
from ..logging_setup import get_logger

log = get_logger("ecosystem.read_interpreter")


@dataclass
class JarvisReadIntent:
    """Structured representation of a parsed read-only ecosystem query."""
    tool_id: str
    confidence: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "confidence": self.confidence,
            "parameters": self.parameters,
            "summary": self.summary,
        }


def get_current_date_kolkata(dt: Optional[datetime.datetime] = None) -> datetime.datetime:
    """Return timezone-aware datetime for Asia/Kolkata or local."""
    if dt is not None:
        return dt
    if ZoneInfo is not None:
        try:
            return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        except Exception:
            pass
    return datetime.datetime.now()


def sanitize_read_prompt(prompt: str) -> Optional[str]:
    """Sanitize prompt and reject prompt injection, SQL, and fake tools."""
    if not prompt or not isinstance(prompt, str):
        return None

    cleaned = prompt.strip().lower()

    # Reject prompt injections, SQL keywords, and fake command executions
    dangerous_patterns = [
        r"ignore\s+(all|previous|system|rules)",
        r"select\s+.*\s+from",
        r"insert\s+into",
        r"update\s+.*\s+set",
        r"delete\s+from",
        r"drop\s+table",
        r"exec(ute)?\s+.*",
        r"union\s+select",
        r"--",
        r"read\.admin\.",
        r"query\.database",
        r"run\.sql",
        r"fetch\.rpc",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, cleaned):
            log.warning(f"Rejected suspicious or injected read query: {prompt}")
            return None

    return cleaned


def interpret_ecosystem_read_query(
    prompt: str, now: Optional[datetime.datetime] = None
) -> Optional[JarvisReadIntent]:
    """Deterministically maps natural language question to a canonical read tool."""
    cleaned = sanitize_read_prompt(prompt)
    if not cleaned:
        return None

    ref_dt = get_current_date_kolkata(now)
    today_str = ref_dt.strftime("%Y-%m-%d")
    tomorrow_str = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 1. DayMentor Tasks Today ──
    if (
        re.search(r"\b(tasks?|study|assignments?|homework)\b.*\b(today)\b", cleaned)
        or re.search(r"\bwhat (do i|should i) (need to )?study today\b", cleaned)
        or re.search(r"\bwhat do i have today\b", cleaned)
        or cleaned in ("tasks today", "study today", "what are my tasks today", "today tasks")
    ):
        return JarvisReadIntent(
            tool_id="read.daymentor.tasks_today",
            confidence=1.0,
            parameters={"target_date": today_str},
            summary="Retrieve DayMentor tasks due today",
        )

    # ── 2. DayMentor Tasks Tomorrow ──
    if (
        re.search(r"\b(tasks?|study|assignments?|homework)\b.*\b(tomorrow)\b", cleaned)
        or re.search(r"\bwhat (do i|should i) (need to )?study tomorrow\b", cleaned)
        or re.search(r"\bwhat do i have tomorrow\b", cleaned)
        or cleaned in ("tasks tomorrow", "study tomorrow", "what are my tasks tomorrow", "tomorrow tasks")
    ):
        return JarvisReadIntent(
            tool_id="read.daymentor.tasks_tomorrow",
            confidence=1.0,
            parameters={"target_date": tomorrow_str},
            summary="Retrieve DayMentor tasks due tomorrow",
        )

    # ── 3. DayMentor Next Exam ──
    if (
        re.search(r"\b(next|upcoming|scheduled)\s+exam\b", cleaned)
        or re.search(r"\bwhen is my (next )?exam\b", cleaned)
        or re.search(r"\bdo i have (an|any) exam\b", cleaned)
        or cleaned in ("next exam", "upcoming exam", "exams")
    ):
        return JarvisReadIntent(
            tool_id="read.daymentor.next_exam",
            confidence=1.0,
            parameters={},
            summary="Retrieve DayMentor next upcoming exam",
        )

    # ── 4. DayMentor Study This Week ──
    if (
        re.search(r"\b(how much|how many hours|how long|stats)\b.*\b(study|studied)\b.*\b(this week|week)\b", cleaned)
        or re.search(r"\bstudy (stats|summary|report|hours) (this )?week\b", cleaned)
        or re.search(r"\bhow active was my study this week\b", cleaned)
    ):
        return JarvisReadIntent(
            tool_id="read.daymentor.study_week",
            confidence=1.0,
            parameters={},
            summary="Retrieve DayMentor study analytics for this week",
        )

    # ── 5. Cricket Last Match ──
    if (
        re.search(r"\b(last|latest|recent|previous)\s+cricket\s+match\b", cleaned)
        or re.search(r"\bwhat was my (last|latest) cricket match\b", cleaned)
        or re.search(r"\bwho did i play against (last|recently)\b", cleaned)
        or cleaned in ("last cricket match", "latest match", "last match")
    ):
        return JarvisReadIntent(
            tool_id="read.cricket.last_match",
            confidence=1.0,
            parameters={},
            summary="Retrieve details of the most recent cricket match",
        )

    # ── 6. Cricket Match Summary ──
    if (
        re.search(r"\bhow many matches (have i|did i|were) (completed|created|played)\b", cleaned)
        or re.search(r"\bcricket (summary|stats|overview|record)\b", cleaned)
        or re.search(r"\bmy cricket matches\b", cleaned)
    ):
        return JarvisReadIntent(
            tool_id="read.cricket.match_summary",
            confidence=1.0,
            parameters={},
            summary="Retrieve Cricket Scorer match aggregates",
        )

    # ── 7. Hackathon Latest Result / Score ──
    if (
        re.search(r"\b(latest|last|recent|best)\s+hackathon\s+(score|result|points)\b", cleaned)
        or re.search(r"\bwhat was my (latest|last) hackathon (score|result)\b", cleaned)
        or cleaned in ("latest hackathon score", "hackathon score", "last hackathon result", "hackathon result")
    ):
        return JarvisReadIntent(
            tool_id="read.hackathon.latest_result",
            confidence=1.0,
            parameters={},
            summary="Retrieve completed Hackathon simulation result",
        )

    # ── 8. Recent Ecosystem Activity ──
    if (
        re.search(r"\bwhat did i do (today|recently)\b", cleaned)
        or re.search(r"\b(recent|latest)\s+(ecosystem\s+)?activity\b", cleaned)
        or re.search(r"\bmy (recent )?activity\b", cleaned)
        or cleaned in ("recent activity", "what did i do today", "my activity")
    ):
        return JarvisReadIntent(
            tool_id="read.ecosystem.recent_activity",
            confidence=1.0,
            parameters={"limit": 10},
            summary="Retrieve recent ecosystem activities",
        )

    # ── 9. Ecosystem Summary / Insights ──
    if (
        re.search(r"\bhow active have i been (this week)?\b", cleaned)
        or re.search(r"\bwhich app (have i|did i) (used?|active) most\b", cleaned)
        or re.search(r"\b(ecosystem|apps?)\s+(summary|insights|stats|usage)\b", cleaned)
        or re.search(r"\bwhat apps have i used (recently)?\b", cleaned)
    ):
        return JarvisReadIntent(
            tool_id="read.ecosystem.summary",
            confidence=1.0,
            parameters={},
            summary="Retrieve overall ecosystem insights summary",
        )

    return None
