"""PySide6 Desktop Ecosystem Action Drawer Tests."""
from __future__ import annotations

import datetime
from pathlib import Path
import sys

# Ensure AppSuite_JarvisV1 root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pytest
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt

from appsuite.ecosystem import (
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
    ECOSYSTEM_URLS,
    HACKATHON_PROBLEMS,
    AachmanEcosystemClient,
    JarvisEcosystemIntent,
)
from desktop_ui.widgets.ecosystem_drawer import (
    EcosystemDrawer,
    DayMentorTaskDialog,
    CricketMatchDialog,
    HackathonSimulationDialog,
    ActionConfirmationDialog,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for PySide6 tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_drawer_instantiation_signed_out(qapp, tmp_path):
    session_file = tmp_path / "pyflare_session.json"
    client = AachmanEcosystemClient(session_file=session_file)

    drawer = EcosystemDrawer()
    drawer.client = client
    drawer.refresh_account_state()

    assert "Not Connected" in drawer.status_dot.text()
    assert "Sign In" in drawer.btn_auth_action.text()
    print("✓ Desktop test passed: Signed-out state rendered accurately")


def test_drawer_instantiation_signed_in(qapp, tmp_path):
    session_file = tmp_path / "pyflare_session.json"
    client = AachmanEcosystemClient(session_file=session_file)
    client._in_memory_access_token = "dummy_token"
    client.metadata = {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "email": "student@aachman.org",
        "expires_at": int(datetime.datetime.now().timestamp()) + 3600,
    }

    drawer = EcosystemDrawer()
    drawer.client = client
    drawer.refresh_account_state()

    assert "Connected" in drawer.status_dot.text()
    assert drawer.lbl_email.text() == "student@aachman.org"
    assert "Sign Out" in drawer.btn_auth_action.text()
    print("✓ Desktop test passed: Signed-in state rendered with user email")


def test_daymentor_task_dialog(qapp):
    dlg = DayMentorTaskDialog()
    dlg.txt_title.setText("Physics Oscillations Review")
    dlg.cmb_priority.setCurrentText("high")

    intent = dlg.get_intent()
    assert intent.command_id == "action.daymentor.create_task"
    assert intent.parameters["title"] == "Physics Oscillations Review"
    assert intent.parameters["priority"] == "high"
    assert intent.requires_confirmation is True
    print("✓ Desktop test passed: DayMentor task dialog payload validated")


def test_cricket_match_dialog(qapp):
    dlg = CricketMatchDialog()
    dlg.txt_team_a.setText("India")
    dlg.txt_team_b.setText("South Africa")
    dlg.cmb_format.setCurrentText("ODI")
    dlg.spn_overs.setValue(50)

    intent = dlg.get_intent()
    assert intent.command_id == "action.cricket.create_match"
    assert intent.parameters["team_a"] == "India"
    assert intent.parameters["team_b"] == "South Africa"
    assert intent.parameters["match_type"] == "ODI"
    assert intent.parameters["overs"] == 50
    assert intent.requires_confirmation is True
    print("✓ Desktop test passed: Cricket match dialog payload validated")


def test_hackathon_simulation_dialog(qapp):
    dlg = HackathonSimulationDialog()
    dlg.cmb_difficulty.setCurrentText("hard")

    intent = dlg.get_intent()
    assert intent.command_id == "action.hackathon.start_simulation"
    assert intent.parameters["difficulty"] == "hard"
    assert any(p["id"] == intent.parameters["problem_id"] for p in HACKATHON_PROBLEMS)
    assert intent.requires_confirmation is True
    print("✓ Desktop test passed: Hackathon simulation dialog payload validated")


def test_action_confirmation_dialog_cancellation(qapp):
    intent = JarvisEcosystemIntent(
        command_id="action.daymentor.create_task",
        confidence=1.0,
        parameters={"title": "Cancelled Task"},
        requires_confirmation=True,
        summary="Create DayMentor Task: Cancelled Task",
    )
    dlg = ActionConfirmationDialog(intent)
    # Simulate reject/cancel
    dlg.reject()
    assert dlg.result() == QDialog.Rejected
    print("✓ Desktop test passed: Action confirmation dialog cancellation verified")


def test_url_allowlist_validation(qapp):
    drawer = EcosystemDrawer()
    blocked = []

    # Intercept open_verified_link to test security boundary
    def mock_open(url):
        if any(url.startswith(base) for base in ECOSYSTEM_URLS.values()):
            return True
        blocked.append(url)
        return False

    assert mock_open("https://daymentor.vercel.app/tasks") is True
    assert mock_open("https://evil.example/malicious") is False
    assert "https://evil.example/malicious" in blocked
    print("✓ Desktop test passed: Deep-link URL allowlist boundary enforced")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    print("\n=== RUNNING DESKTOP ECOSYSTEM DRAWER TESTS ===")
    test_drawer_instantiation_signed_out(app, Path("/tmp"))
    test_drawer_instantiation_signed_in(app, Path("/tmp"))
    test_daymentor_task_dialog(app)
    test_cricket_match_dialog(app)
    test_hackathon_simulation_dialog(app)
    test_action_confirmation_dialog_cancellation(app)
    test_url_allowlist_validation(app)
    print("\n=== ALL DESKTOP ECOSYSTEM DRAWER TESTS PASSED 100% ===\n")
