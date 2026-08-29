"""Unit and Integration Tests for Ecosystem Action Idempotency Hardening v1."""
from __future__ import annotations

import concurrent.futures
from pathlib import Path
import sys
import uuid

# Ensure AppSuite_JarvisV1 root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from appsuite.ecosystem import (
    AachmanEcosystemClient,
    EcosystemExecutor,
    JarvisEcosystemIntent,
)


class MockIdempotentSupabaseServer:
    """Mock server simulating PostgreSQL execute_ecosystem_action with unique index on (user_id, idempotency_key)."""

    def __init__(self):
        self.commands_table = {}  # (user_id, idempotency_key) -> command_record
        self.daymentor_tasks = []
        self.cricket_matches = []
        self.hackathon_runs = []
        self.user_activities = []

    def handle_rpc(self, user_id: str, action_type: str, payload: dict, idempotency_key: str | None) -> dict:
        key = (user_id, idempotency_key) if idempotency_key else None

        # 1. Check existing command by (user_id, idempotency_key)
        if key and key in self.commands_table:
            rec = self.commands_table[key]
            if rec["status"] == "completed":
                return rec["result"]
            elif rec["status"] == "pending":
                return {"success": False, "status": "pending", "message": "Command execution in progress."}
            else:
                return {"success": False, "error": rec.get("error_message", "Failed")}

        # 2. Claim pending command
        cmd_id = str(uuid.uuid4())
        if key:
            self.commands_table[key] = {
                "id": cmd_id,
                "user_id": user_id,
                "action_type": action_type,
                "payload": payload,
                "status": "pending",
                "idempotency_key": idempotency_key,
            }

        # 3. Perform Target Mutation
        entity_id = ""
        deep_link = ""
        if action_type == "daymentor.create_task":
            entity_id = f"task_{len(self.daymentor_tasks) + 1}"
            self.daymentor_tasks.append({"id": entity_id, "title": payload.get("title")})
            deep_link = "https://daymentor.vercel.app/tasks"
            self.user_activities.append({"app_id": "daymentor", "event_key": f"daymentor_task_{entity_id}"})

        elif action_type == "cricket_scorer.create_match":
            entity_id = f"match_{len(self.cricket_matches) + 1}"
            self.cricket_matches.append({"id": entity_id, "teams": f"{payload.get('team_a')} vs {payload.get('team_b')}"})
            deep_link = f"https://cricket-scorer.vercel.app/match/{entity_id}"
            self.user_activities.append({"app_id": "cricket_scorer", "event_key": f"cricket_match_{entity_id}"})

        elif action_type == "hackathon_simulator.start_simulation":
            entity_id = f"sim_{len(self.hackathon_runs) + 1}"
            self.hackathon_runs.append({"id": entity_id, "problem": payload.get("problem_title")})
            deep_link = f"https://the-hackathon-simulator.vercel.app/game?simId={entity_id}"
            self.user_activities.append({"app_id": "hackathon_simulator", "event_key": f"hackathon_sim_{entity_id}"})

        result = {
            "success": True,
            "command_id": cmd_id,
            "action_type": action_type,
            "entity_id": entity_id,
            "deep_link": deep_link,
        }

        # 4. Mark Completed
        if key:
            self.commands_table[key]["status"] = "completed"
            self.commands_table[key]["result"] = result

        return result


def test_sequential_duplicate_idempotency():
    mock_server = MockIdempotentSupabaseServer()
    client = AachmanEcosystemClient(session_file=Path("/tmp/mock_session.json"))
    client._in_memory_access_token = "dummy_token"
    client.metadata = {"user_id": "user_123", "email": "test@aachman.org"}

    # Mock execute_ecosystem_action
    client.execute_ecosystem_action = lambda action_type, payload, idempotency_key=None: mock_server.handle_rpc(
        "user_123", action_type, payload, idempotency_key
    )

    executor = EcosystemExecutor(client)
    fixed_key = "idemp_test_001"
    intent = JarvisEcosystemIntent(
        command_id="action.daymentor.create_task",
        confidence=1.0,
        parameters={"title": "Physics revision", "priority": "high", "deadline": "2026-08-30"},
        requires_confirmation=False,
        summary="Create Physics revision task",
        idempotency_key=fixed_key,
    )

    # First Call
    res1 = executor.execute_intent(intent, confirm=True)
    assert res1.status == "success"
    assert len(mock_server.daymentor_tasks) == 1
    assert len(mock_server.user_activities) == 1
    assert len(mock_server.commands_table) == 1

    # Second Call with SAME idempotency key (e.g. retry / double-submit)
    res2 = executor.execute_intent(intent, confirm=True)
    assert res2.status == "success"
    # Target entities, commands, and activities MUST remain exactly 1!
    assert len(mock_server.daymentor_tasks) == 1
    assert len(mock_server.user_activities) == 1
    assert len(mock_server.commands_table) == 1
    print("✓ Sequential idempotency test passed: Repeated call produced 0 duplicate rows")


def test_concurrent_same_key_safety():
    mock_server = MockIdempotentSupabaseServer()
    client = AachmanEcosystemClient(session_file=Path("/tmp/mock_session.json"))
    client._in_memory_access_token = "dummy_token"
    client.metadata = {"user_id": "user_123", "email": "test@aachman.org"}

    client.execute_ecosystem_action = lambda action_type, payload, idempotency_key=None: mock_server.handle_rpc(
        "user_123", action_type, payload, idempotency_key
    )

    executor = EcosystemExecutor(client)
    fixed_key = "idemp_concurrent_002"
    intent = JarvisEcosystemIntent(
        command_id="action.cricket.create_match",
        confidence=1.0,
        parameters={"team_a": "India", "team_b": "Australia", "match_type": "T20", "overs": 20},
        requires_confirmation=False,
        summary="Create Cricket Match",
        idempotency_key=fixed_key,
    )

    # Submit concurrently from two simulated clients (Desktop + CLI)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(executor.execute_intent, intent, True)
        f2 = ex.submit(executor.execute_intent, intent, True)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status == "success"
    assert r2.status == "success"
    # Exactly 1 match created
    assert len(mock_server.cricket_matches) == 1
    assert len(mock_server.commands_table) == 1
    print("✓ Concurrent idempotency test passed: Parallel requests safely resolved to single mutation")


def test_different_key_same_payload_allowed():
    mock_server = MockIdempotentSupabaseServer()
    client = AachmanEcosystemClient(session_file=Path("/tmp/mock_session.json"))
    client._in_memory_access_token = "dummy_token"
    client.metadata = {"user_id": "user_123", "email": "test@aachman.org"}

    client.execute_ecosystem_action = lambda action_type, payload, idempotency_key=None: mock_server.handle_rpc(
        "user_123", action_type, payload, idempotency_key
    )

    executor = EcosystemExecutor(client)
    intent1 = JarvisEcosystemIntent(
        command_id="action.daymentor.create_task",
        confidence=1.0,
        parameters={"title": "Physics revision"},
        requires_confirmation=False,
        summary="Create Physics revision",
        idempotency_key="key_attempt_A",
    )
    intent2 = JarvisEcosystemIntent(
        command_id="action.daymentor.create_task",
        confidence=1.0,
        parameters={"title": "Physics revision"},
        requires_confirmation=False,
        summary="Create Physics revision",
        idempotency_key="key_attempt_B",
    )

    executor.execute_intent(intent1, confirm=True)
    executor.execute_intent(intent2, confirm=True)

    # When user intentionally submits distinct commands, 2 tasks are created
    assert len(mock_server.daymentor_tasks) == 2
    assert len(mock_server.commands_table) == 2
    print("✓ Different key test passed: Distinct user actions with same payload executed cleanly")


def test_cross_user_key_isolation():
    mock_server = MockIdempotentSupabaseServer()

    # User A submits with Key X
    res_a = mock_server.handle_rpc("user_A", "daymentor.create_task", {"title": "User A Task"}, "shared_key_X")
    assert res_a["success"] is True

    # User B submits with same Key X -> Should create User B's separate command
    res_b = mock_server.handle_rpc("user_B", "daymentor.create_task", {"title": "User B Task"}, "shared_key_X")
    assert res_b["success"] is True

    assert len(mock_server.daymentor_tasks) == 2
    assert len(mock_server.commands_table) == 2
    print("✓ Cross-user key isolation test passed: Scoped strictly to (user_id, idempotency_key)")


if __name__ == "__main__":
    print("\n=== RUNNING ECOSYSTEM IDEMPOTENCY HARDENING TESTS ===")
    test_sequential_duplicate_idempotency()
    test_concurrent_same_key_safety()
    test_different_key_same_payload_allowed()
    test_cross_user_key_isolation()
    print("\n=== ALL ECOSYSTEM IDEMPOTENCY TESTS PASSED 100% ===\n")
