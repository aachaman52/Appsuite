"""Read Executor and Natural Language Formatter for Jarvis Ecosystem Intelligence v1.

Executes canonical read tools strictly against authenticated user data:
- Zero entity writes
- Zero user_activity writes
- Zero ecosystem_commands writes
- Fully formatted, human-friendly natural language responses
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

from .client import AachmanEcosystemClient, get_ecosystem_client
from .constants import JARVIS_ALLOWED_READ_TOOL_IDS
from .read_interpreter import JarvisReadIntent
from ..logging_setup import get_logger

log = get_logger("ecosystem.read_executor")


@dataclass
class JarvisReadResponse:
    """Structured and human-formatted response for a read query."""
    tool_id: str
    status: str  # "success", "empty", "unauthenticated", "error"
    human_text: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "status": self.status,
            "human_text": self.human_text,
            "data": self.data,
        }


class EcosystemReadExecutor:
    """Safe, read-only ecosystem query executor."""

    def __init__(self, client: Optional[AachmanEcosystemClient] = None):
        self.client = client or get_ecosystem_client()

    def execute_read_intent(self, intent: JarvisReadIntent) -> JarvisReadResponse:
        """Validate and dispatch read intent without modifying any state."""
        # 1. Allowlist validation
        if intent.tool_id not in JARVIS_ALLOWED_READ_TOOL_IDS:
            log.warning(f"Blocked unauthorized read tool ID: {intent.tool_id}")
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="error",
                human_text="I don't have access to that type of information.",
                data={"error": "Unsupported tool ID"},
            )

        # 2. Authentication check
        if not self.client.is_authenticated:
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="unauthenticated",
                human_text="Please sign in to your Aachman Account to access your personal ecosystem information.",
                data={"error": "Authentication required"},
            )

        access_token = self.client.get_valid_access_token()
        if not access_token:
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="unauthenticated",
                human_text="Your session has expired. Please sign in to your Aachman Account again.",
                data={"error": "Session expired"},
            )

        try:
            # 3. Route to specific read handlers
            if intent.tool_id == "read.daymentor.tasks_today":
                return self._read_daymentor_tasks(intent.parameters.get("target_date"), "today")

            elif intent.tool_id == "read.daymentor.tasks_tomorrow":
                return self._read_daymentor_tasks(intent.parameters.get("target_date"), "tomorrow")

            elif intent.tool_id == "read.daymentor.next_exam":
                return self._read_daymentor_next_exam()

            elif intent.tool_id == "read.daymentor.study_week":
                return self._read_daymentor_study_week()

            elif intent.tool_id == "read.cricket.last_match":
                return self._read_cricket_last_match()

            elif intent.tool_id == "read.cricket.match_summary":
                return self._read_cricket_summary()

            elif intent.tool_id == "read.hackathon.latest_result":
                return self._read_hackathon_latest_result()

            elif intent.tool_id == "read.ecosystem.recent_activity":
                return self._read_recent_activity(intent.parameters.get("limit", 10))

            elif intent.tool_id == "read.ecosystem.summary":
                return self._read_ecosystem_summary()

            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="error",
                human_text="Unable to process this query.",
                data={},
            )

        except requests.exceptions.Timeout:
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="error",
                human_text="The connection to your Aachman ecosystem timed out. Please try again.",
                data={"error": "Timeout"},
            )
        except requests.exceptions.ConnectionError:
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="error",
                human_text="I can't reach your Aachman ecosystem right now (offline mode).",
                data={"error": "Connection error"},
            )
        except Exception as e:
            log.error(f"Read tool execution failed: {e}")
            return JarvisReadResponse(
                tool_id=intent.tool_id,
                status="error",
                human_text="An error occurred while retrieving your ecosystem data.",
                data={"error": str(e)},
            )

    # ── Tool Implementations ──────────────────────────────────────────────────

    def _rpc(self, fn_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Safe server-side RPC caller using user JWT token."""
        url = f"{self.client.supabase_url}/rest/v1/rpc/{fn_name}"
        headers = {
            "apikey": self.client.supabase_key,
            "Authorization": f"Bearer {self.client.get_valid_access_token()}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, json=params or {}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None

    def _read_daymentor_tasks(self, target_date: Optional[str], label: str) -> JarvisReadResponse:
        # Try RPC first, fallback to user_data endpoint
        res = self._rpc("get_daymentor_tasks_for_date", {"p_date": target_date})
        tasks = []
        if res and res.get("success"):
            tasks = res.get("tasks", [])
        else:
            # Fallback client-side parse of daymentor_user_data
            url = f"{self.client.supabase_url}/rest/v1/daymentor_user_data?user_id=eq.{self.client.user_id}"
            headers = {
                "apikey": self.client.supabase_key,
                "Authorization": f"Bearer {self.client.get_valid_access_token()}",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.json():
                dm_data = resp.json()[0].get("data", {})
                all_tasks = dm_data.get("tasks", [])
                tasks = [t for t in all_tasks if t.get("deadline") == target_date]

        if not tasks:
            return JarvisReadResponse(
                tool_id=f"read.daymentor.tasks_{label}",
                status="empty",
                human_text=f"You don't have any DayMentor tasks scheduled for {label}.",
                data={"tasks": [], "count": 0, "date": target_date},
            )

        lines = [f"You have {len(tasks)} DayMentor task{'s' if len(tasks) > 1 else ''} due {label}:"]
        for idx, t in enumerate(tasks, 1):
            title = t.get("title", "Untitled Task")
            pri = t.get("priority", "medium").capitalize()
            comp = " [Completed]" if t.get("completed") else ""
            lines.append(f"  {idx}. {title} ({pri} Priority){comp}")

        return JarvisReadResponse(
            tool_id=f"read.daymentor.tasks_{label}",
            status="success",
            human_text="\n".join(lines),
            data={"tasks": tasks, "count": len(tasks), "date": target_date},
        )

    def _read_daymentor_next_exam(self) -> JarvisReadResponse:
        res = self._rpc("get_daymentor_next_exam")
        has_exam = False
        exam = None
        days_rem = None

        if res and res.get("success") and res.get("has_exam"):
            has_exam = True
            exam = res.get("exam")
            days_rem = res.get("days_remaining")
        else:
            # Fallback client-side
            url = f"{self.client.supabase_url}/rest/v1/daymentor_user_data?user_id=eq.{self.client.user_id}"
            headers = {
                "apikey": self.client.supabase_key,
                "Authorization": f"Bearer {self.client.get_valid_access_token()}",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.json():
                dm_data = resp.json()[0].get("data", {})
                exams = dm_data.get("exams", [])
                if exams:
                    exam = sorted(exams, key=lambda x: x.get("date", ""))[-1]
                    has_exam = True

        if not has_exam or not exam:
            return JarvisReadResponse(
                tool_id="read.daymentor.next_exam",
                status="empty",
                human_text="You don't have any upcoming exams scheduled in DayMentor.",
                data={"has_exam": False},
            )

        subj = exam.get("subjectName") or exam.get("subjectId") or "Exam"
        dt = exam.get("date", "Upcoming")
        days_text = f" (in {days_rem} days)" if days_rem is not None else ""
        text = f"Your next scheduled exam is {subj} on {dt}{days_text}."

        return JarvisReadResponse(
            tool_id="read.daymentor.next_exam",
            status="success",
            human_text=text,
            data={"has_exam": True, "exam": exam, "days_remaining": days_rem},
        )

    def _read_daymentor_study_week(self) -> JarvisReadResponse:
        insights = self._rpc("get_ecosystem_insights") or {}
        dm_stats = insights.get("daymentor", {})

        mins = dm_stats.get("studyMinutes", 0)
        sessions = dm_stats.get("studySessions", 0)
        tasks_comp = dm_stats.get("tasksCompleted", 0)
        streak = dm_stats.get("streak", 0)

        hours = round(mins / 60, 1)
        text = (
            f"Here is your DayMentor study summary for this week:\n"
            f"  • Study Time: {mins} minutes ({hours} hours)\n"
            f"  • Focus Sessions: {sessions}\n"
            f"  • Tasks Completed: {tasks_comp}\n"
            f"  • Current Streak: {streak} days"
        )

        return JarvisReadResponse(
            tool_id="read.daymentor.study_week",
            status="success",
            human_text=text,
            data={"minutes": mins, "sessions": sessions, "tasks_completed": tasks_comp, "streak": streak},
        )

    def _read_cricket_last_match(self) -> JarvisReadResponse:
        res = self._rpc("get_cricket_last_match")
        has_match = False
        match = None

        if res and res.get("success") and res.get("has_match"):
            has_match = True
            match = res.get("match")
        else:
            url = f"{self.client.supabase_url}/rest/v1/cricket_matches?user_id=eq.{self.client.user_id}&order=created_at.desc&limit=1"
            headers = {
                "apikey": self.client.supabase_key,
                "Authorization": f"Bearer {self.client.get_valid_access_token()}",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.json():
                match = resp.json()[0]
                has_match = True

        if not has_match or not match:
            return JarvisReadResponse(
                tool_id="read.cricket.last_match",
                status="empty",
                human_text="You don't have any cricket matches recorded yet in Cricket Scorer.",
                data={"has_match": False},
            )

        team_a = match.get("team_a", "Team A")
        team_b = match.get("team_b", "Team B")
        m_type = match.get("match_type", "T20")
        score = match.get("score_line") or match.get("result") or "Match in progress"
        status = "Completed" if match.get("completed") else "Created / In Progress"

        text = f"Your last cricket match was {team_a} vs {team_b} ({m_type}).\nStatus: {status}\nScore / Summary: {score}"

        return JarvisReadResponse(
            tool_id="read.cricket.last_match",
            status="success",
            human_text=text,
            data={"has_match": True, "match": match},
        )

    def _read_cricket_summary(self) -> JarvisReadResponse:
        insights = self._rpc("get_ecosystem_insights") or {}
        cs_stats = insights.get("cricketScorer", {})

        created = cs_stats.get("matchesCreated", 0)
        completed = cs_stats.get("matchesCompleted", 0)
        tournaments = cs_stats.get("tournaments", 0)

        text = (
            f"Cricket Scorer Summary:\n"
            f"  • Matches Created: {created}\n"
            f"  • Matches Completed: {completed}\n"
            f"  • Tournaments Organized: {tournaments}"
        )

        return JarvisReadResponse(
            tool_id="read.cricket.match_summary",
            status="success",
            human_text=text,
            data={"matches_created": created, "matches_completed": completed, "tournaments": tournaments},
        )

    def _read_hackathon_latest_result(self) -> JarvisReadResponse:
        res = self._rpc("get_hackathon_latest_result")
        has_result = False
        result = None

        if res and res.get("success") and res.get("has_result"):
            has_result = True
            result = res.get("result")
        else:
            # Query user_activity for simulation_completed only
            url = f"{self.client.supabase_url}/rest/v1/user_activity?user_id=eq.{self.client.user_id}&app_id=eq.hackathon_simulator&activity_type=eq.simulation_completed&order=occurred_at.desc&limit=1"
            headers = {
                "apikey": self.client.supabase_key,
                "Authorization": f"Bearer {self.client.get_valid_access_token()}",
            }
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and resp.json():
                act = resp.json()[0]
                has_result = True
                result = {
                    "title": act.get("title"),
                    "score": act.get("metadata", {}).get("score"),
                    "difficulty": act.get("metadata", {}).get("difficulty", "medium"),
                }

        if not has_result or not result:
            return JarvisReadResponse(
                tool_id="read.hackathon.latest_result",
                status="empty",
                human_text="I couldn't find a completed hackathon simulation result yet.",
                data={"has_result": False},
            )

        title = result.get("title") or result.get("problem_title") or "Hackathon Challenge"
        score = result.get("score")
        diff = result.get("difficulty", "medium").capitalize()
        score_text = f"with a final score of {score}/100" if score is not None else "completed"

        text = f"Your latest completed hackathon simulation was '{title}' ({diff} Difficulty) {score_text}."

        return JarvisReadResponse(
            tool_id="read.hackathon.latest_result",
            status="success",
            human_text=text,
            data={"has_result": True, "result": result},
        )

    def _read_recent_activity(self, limit: int = 10) -> JarvisReadResponse:
        activities = self.client.fetch_recent_activity(limit=limit)
        if not activities:
            return JarvisReadResponse(
                tool_id="read.ecosystem.recent_activity",
                status="empty",
                human_text="You don't have any recent ecosystem activity recorded yet.",
                data={"activities": [], "count": 0},
            )

        lines = ["Here is your recent ecosystem activity:"]
        for idx, act in enumerate(activities, 1):
            app = act.get("app_id", "").replace("_", " ").title()
            title = act.get("title", "")
            sub = act.get("subtitle", "")
            lines.append(f"  {idx}. [{app}] {title} — {sub}")

        return JarvisReadResponse(
            tool_id="read.ecosystem.recent_activity",
            status="success",
            human_text="\n".join(lines),
            data={"activities": activities, "count": len(activities)},
        )

    def _read_ecosystem_summary(self) -> JarvisReadResponse:
        insights = self._rpc("get_ecosystem_insights")
        if not insights:
            return JarvisReadResponse(
                tool_id="read.ecosystem.summary",
                status="empty",
                human_text="No ecosystem analytics recorded yet. Start using DayMentor, Cricket Scorer, or Hackathon Simulator to build your profile insights.",
                data={},
            )

        overview = insights.get("overview", {})
        apps_used = overview.get("appsUsed", 0)
        total_act = overview.get("totalActivities", 0)
        week_act = overview.get("activitiesThisWeek", 0)
        most_used = (overview.get("mostUsedApp") or "None").replace("_", " ").title()

        text = (
            f"Aachman Ecosystem Summary:\n"
            f"  • Connected Apps Used: {apps_used} of 4\n"
            f"  • Activities This Week: {week_act}\n"
            f"  • Total Lifetime Actions: {total_act}\n"
            f"  • Most Active App: {most_used}"
        )

        return JarvisReadResponse(
            tool_id="read.ecosystem.summary",
            status="success",
            human_text=text,
            data=insights,
        )
