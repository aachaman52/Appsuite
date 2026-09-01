"""Shared deterministic planning and scheduling helpers.

Unifies deadline, urgency, normalization, and deduplication logic
between single-step EcosystemPlanner and multi-step GoalPlanner.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Tuple


def normalize_subject(text: str) -> str:
    """Normalize subject or title for duplicate comparison."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\b(exam|revision|review|test|preparation|study|homework|practice|mock)\b", "", t)
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def is_duplicate_task(suggested_title: str, existing_tasks: List[Dict[str, Any]]) -> bool:
    """Determine if a task covering the same subject/topic already exists."""
    norm_sugg = normalize_subject(suggested_title)
    if not norm_sugg:
        return False

    for task in existing_tasks:
        if not isinstance(task, dict):
            continue
        norm_exist = normalize_subject(task.get("title", ""))
        if not norm_exist:
            continue
        if norm_sugg == norm_exist or norm_sugg in norm_exist or norm_exist in norm_sugg:
            return True
    return False


def calculate_exam_revision_schedule(
    exam_data: Dict[str, Any],
    ref_dt: datetime.datetime,
) -> Dict[str, Any]:
    """Calculate deterministic revision deadline, priority, and problem set schedule.

    Rules:
    - days_remaining == 0 (Exam Today): deadline = today, priority = high
    - days_remaining == 1 (Exam Tomorrow): deadline = today, priority = high
    - days_remaining == 2 (Exam in 2 days): deadline = tomorrow, priority = high
    - days_remaining >= 3: primary revision due tomorrow (medium/high), practice questions due in min(2, days_remaining - 1) days.
    """
    exam_dict = exam_data.get("exam") if isinstance(exam_data.get("exam"), dict) else exam_data
    days_rem = exam_data.get("days_remaining") if "days_remaining" in exam_data else exam_dict.get("days_remaining", 999)
    if days_rem is None:
        days_rem = 999
    subject = exam_dict.get("subjectName") or exam_dict.get("subjectId") or "Subject"
    exam_date = exam_dict.get("date", "Upcoming")

    today_str = ref_dt.strftime("%Y-%m-%d")
    tomorrow_str = (ref_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")


    if days_rem <= 0:
        # Exam is TODAY
        rev_deadline = today_str
        rev_priority = "high"
        has_practice = False
        practice_deadline = None
    elif days_rem == 1:
        # Exam is TOMORROW
        rev_deadline = today_str
        rev_priority = "high"
        has_practice = False
        practice_deadline = None
    elif days_rem == 2:
        # Exam is in 2 days
        rev_deadline = tomorrow_str
        rev_priority = "high"
        has_practice = False
        practice_deadline = None
    elif days_rem == 3:
        # Exam is in 3 days (High urgency + practice problem set)
        rev_deadline = tomorrow_str
        rev_priority = "high"
        has_practice = True
        offset = min(2, days_rem - 1)
        practice_deadline = (ref_dt + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
    else:
        # Exam is >= 4 days away
        rev_deadline = tomorrow_str
        rev_priority = "medium"
        has_practice = True
        offset = min(2, days_rem - 1)
        practice_deadline = (ref_dt + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")


    return {
        "subject": subject,
        "exam_date": exam_date,
        "days_remaining": days_rem,
        "revision_title": f"{subject} revision",
        "revision_deadline": rev_deadline,
        "revision_priority": rev_priority,
        "has_practice": has_practice,
        "practice_title": f"{subject} practice questions",
        "practice_deadline": practice_deadline,
        "practice_priority": "medium",
    }
