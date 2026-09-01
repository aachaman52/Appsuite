"""Canonical validation for ecosystem write action parameters.

Shared between PlanStore, GoalPlanner, EcosystemPlanner, EcosystemExecutor,
pre-dispatch guards, and desktop UI.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from .constants import HACKATHON_PROBLEMS

# Write-only ecosystem command IDs
WRITE_ACTION_COMMAND_IDS = frozenset({
    "action.daymentor.create_task",
    "action.cricket.create_match",
    "action.hackathon.start_simulation",
})

# Canonical schema contracts
# Format: (field_name, expected_type_or_tuple, required, allowed_enums)
CANONICAL_ACTION_SCHEMAS: Dict[str, List[Tuple[str, Any, bool, Optional[frozenset]]]] = {
    "action.daymentor.create_task": [
        ("title", str, True, None),
        ("priority", str, False, frozenset({"low", "medium", "high"})),
        ("deadline", str, False, None),  # validated as ISO date or empty
        ("subject_id", str, False, None),
        ("difficulty", str, False, frozenset({"easy", "medium", "hard"})),
    ],
    "action.cricket.create_match": [
        ("team_a", str, True, None),
        ("team_b", str, True, None),
        ("match_type", str, False, frozenset({"T20", "ODI", "Test"})),
        ("overs", int, False, None),  # whole integer 1..100
    ],
    "action.hackathon.start_simulation": [
        ("problem_id", str, True, None),  # verified against catalog
        ("problem_title", str, False, None),
        ("difficulty", str, False, frozenset({"easy", "medium", "hard"})),
    ],
}

# Catalog of valid problem IDs
VALID_HACKATHON_PROBLEM_IDS = frozenset(p["id"] for p in HACKATHON_PROBLEMS)


def validate_action_parameters(command_id: str, parameters: Any) -> Optional[str]:
    """Validate action parameters against the single canonical contract.

    Returns:
        None if valid, or a descriptive error string if invalid.
    """
    if command_id not in WRITE_ACTION_COMMAND_IDS:
        return f"Unknown or unauthorized write command ID: '{command_id}'"

    if not isinstance(parameters, dict):
        return f"Parameters for '{command_id}' must be a dict, got {type(parameters).__name__}"

    schema = CANONICAL_ACTION_SCHEMAS.get(command_id)
    if not schema:
        return f"No schema defined for command '{command_id}'"

    allowed_fields = {field_name for field_name, _, _, _ in schema}

    # Strict: reject unexpected parameters
    for key in parameters:
        if key not in allowed_fields:
            return f"Unexpected parameter '{key}' for command '{command_id}'. Allowed: {sorted(allowed_fields)}"

    # Check fields, types, constraints, and enums
    for field_name, field_type, required, allowed_enums in schema:
        value = parameters.get(field_name)
        if value is None:
            if required:
                return f"Missing required parameter '{field_name}' for command '{command_id}'"
            continue

        # Exact type checks (note: bool is a subclass of int in Python, so check bool separately)
        if field_type is int:
            if isinstance(value, bool) or not isinstance(value, int):
                return (
                    f"Parameter '{field_name}' for '{command_id}' must be an integer, "
                    f"got {type(value).__name__}"
                )
        elif not isinstance(value, field_type):
            type_name = field_type.__name__ if isinstance(field_type, type) else str(field_type)
            return (
                f"Parameter '{field_name}' for '{command_id}' must be {type_name}, "
                f"got {type(value).__name__}"
            )

        # String constraints
        if isinstance(value, str):
            trimmed = value.strip()
            if required and len(trimmed) == 0:
                return f"Parameter '{field_name}' for '{command_id}' cannot be empty or whitespace"
            if len(value) > 300:
                return f"Parameter '{field_name}' for '{command_id}' exceeds maximum length (300 chars)"

        # Enum constraints
        if allowed_enums and value not in allowed_enums:
            return (
                f"Parameter '{field_name}' value '{value}' is not valid for '{command_id}'. "
                f"Allowed: {sorted(allowed_enums)}"
            )

        # Domain-specific constraints
        if command_id == "action.daymentor.create_task":
            if field_name == "deadline" and value:
                # Validate date format YYYY-MM-DD
                try:
                    datetime.date.fromisoformat(value)
                except ValueError:
                    return f"Parameter 'deadline' must be a valid ISO date string (YYYY-MM-DD), got '{value}'"

        elif command_id == "action.cricket.create_match":
            if field_name == "overs" and (value <= 0 or value > 100):
                return f"Parameter 'overs' must be a positive integer between 1 and 100, got {value}"

    # Multi-field checks
    if command_id == "action.cricket.create_match":
        team_a = str(parameters.get("team_a", "")).strip().lower()
        team_b = str(parameters.get("team_b", "")).strip().lower()
        if team_a and team_b and team_a == team_b:
            return "Team A and Team B cannot be the same team"

    elif command_id == "action.hackathon.start_simulation":
        problem_id = parameters.get("problem_id")
        if not problem_id or not isinstance(problem_id, str) or len(problem_id.strip()) == 0:
            return "Parameter 'problem_id' cannot be empty or whitespace"
        if len(problem_id) > 100:
            return "Parameter 'problem_id' exceeds maximum length (100 chars)"

    return None

