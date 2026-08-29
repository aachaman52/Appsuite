"""Ecosystem constants and strict command allowlists."""
from typing import Dict, List

# Strict Allowlist of Supported Ecosystem Command IDs
JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS = [
    "app.open.aachman_hub",
    "app.open.daymentor",
    "app.open.cricket_scorer",
    "app.open.hackathon_simulator",
    "action.daymentor.create_task",
    "action.cricket.create_match",
    "action.hackathon.start_simulation",
]

# Strict Allowlist of Supported Ecosystem Read Tool IDs
JARVIS_ALLOWED_READ_TOOL_IDS = [
    "read.daymentor.tasks_today",
    "read.daymentor.tasks_tomorrow",
    "read.daymentor.next_exam",
    "read.daymentor.study_week",
    "read.cricket.last_match",
    "read.cricket.match_summary",
    "read.hackathon.latest_result",
    "read.ecosystem.recent_activity",
    "read.ecosystem.summary",
]

# Trusted Official Ecosystem URLs
ECOSYSTEM_URLS: Dict[str, str] = {
    "app.open.aachman_hub": "https://aachman-hub.vercel.app",
    "app.open.daymentor": "https://daymentor.vercel.app",
    "app.open.cricket_scorer": "https://cricket-scorer.vercel.app",
    "app.open.hackathon_simulator": "https://the-hackathon-simulator.vercel.app",
}

# Supabase Unified Project Credentials (Standard Public Anon/Publishable Client)
DEFAULT_SUPABASE_URL = "https://pazkkzfdiwpcguoghlus.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhemtremZkaXdwY2d1b2dobHVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0NjM2NjEsImV4cCI6MjA5ODAzOTY2MX0.HxBeb4p1mvbz1aFUPfPOJx47aj1SCCjK2WLQkcNoz0U"

# Valid Hackathon Problem Statements
HACKATHON_PROBLEMS: List[Dict[str, str]] = [
    {"id": "prob-learnflow", "title": "LearnFlow AI (Adaptive Study Planner)"},
    {"id": "prob-quizwiz", "title": "QuizWiz Games (Gamified Algorithm Learning)"},
    {"id": "prob-eduscribe", "title": "EduScribe Assistant (Audio Note Transcriber)"},
    {"id": "prob-codequest", "title": "CodeQuest RPG (Coding Maze RPG)"},
    {"id": "prob-vitalsync", "title": "VitalSync Health (Real-time Metric Tracker)"},
]
