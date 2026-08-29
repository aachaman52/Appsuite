"""PyFlare Desktop Ecosystem Action Drawer (PySide6).

Integrates the Aachman Studios Ecosystem directly into PyFlare's desktop workspace:
- Account Header & Session Status
- Secure Login & Sign Out dialogs
- Quick Actions (DayMentor Task, Cricket Match, Hackathon Simulation)
- Action Confirmation Preview Dialogs
- Connected App Launcher (Aachman Hub, DayMentor, Cricket Scorer, Hackathon Simulator)
- Recent Ecosystem Activity with verified deep-link opening
- Non-blocking background worker execution using QThreadPool
"""
from __future__ import annotations

import sys
import webbrowser
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import (
    QDate,
    QObject,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from appsuite.ecosystem import (
    ECOSYSTEM_URLS,
    HACKATHON_PROBLEMS,
    JARVIS_ALLOWED_ECOSYSTEM_COMMAND_IDS,
    AachmanEcosystemClient,
    EcosystemExecutor,
    ExecutionResult,
    JarvisEcosystemIntent,
    get_ecosystem_client,
    interpret_ecosystem_query,
)
from appsuite.logging_setup import get_logger

log = get_logger("desktop.ecosystem_drawer")


# ─── Background Worker ────────────────────────────────────────────────────────
class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)


class EcosystemWorker(QRunnable):
    """Executes network calls in a background thread to prevent UI freezing."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# ─── Dialogs ──────────────────────────────────────────────────────────────────
class EcosystemLoginDialog(QDialog):
    """Secure Aachman Account Login Dialog."""

    def __init__(self, client: AachmanEcosystemClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Aachman Account Sign In")
        self.setFixedSize(380, 260)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            QLabel {
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QLineEdit {
                background-color: #242424;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #00ff66;
            }
            QPushButton#PrimaryBtn {
                background-color: #00ff66;
                color: #121212;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #00dd55;
            }
            QPushButton#SecondaryBtn {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #383838;
                color: #ffffff;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Sign In to Aachman Account", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ff66;")
        layout.addWidget(title)

        desc = QLabel("Authenticate once to sync with DayMentor, Cricket Scorer, and Hub.", self)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc)

        layout.addWidget(QLabel("Email", self))
        self.txt_email = QLineEdit(self)
        self.txt_email.setPlaceholderText("user@example.com")
        layout.addWidget(self.txt_email)

        layout.addWidget(QLabel("Password", self))
        self.txt_password = QLineEdit(self)
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("••••••••")
        self.txt_password.returnPressed.connect(self.handle_login)
        layout.addWidget(self.txt_password)

        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("color: #ff4444; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_login = QPushButton("Sign In", self)
        self.btn_login.setObjectName("PrimaryBtn")
        self.btn_login.clicked.connect(self.handle_login)
        btn_layout.addWidget(self.btn_login)

        layout.addLayout(btn_layout)

    def handle_login(self):
        email = self.txt_email.text().strip()
        password = self.txt_password.text()

        if not email or not password:
            self.lbl_status.setText("Please enter both email and password.")
            return

        self.btn_login.setEnabled(False)
        self.lbl_status.setText("Signing in securely...")
        self.lbl_status.setStyleSheet("color: #00ff66; font-size: 11px;")

        # Background login
        worker = EcosystemWorker(self.client.sign_in, email, password)

        def on_result(res: dict):
            self.btn_login.setEnabled(True)
            if res.get("success"):
                self.accept()
            else:
                self.lbl_status.setText(res.get("error", "Sign in failed."))
                self.lbl_status.setStyleSheet("color: #ff4444; font-size: 11px;")

        def on_error(err_str: str):
            self.btn_login.setEnabled(True)
            self.lbl_status.setText("Connection failed. Check network.")
            self.lbl_status.setStyleSheet("color: #ff4444; font-size: 11px;")

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)


class DayMentorTaskDialog(QDialog):
    """DayMentor Task Form Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add DayMentor Task")
        self.setFixedSize(380, 290)
        self.setModal(True)
        self.setStyleSheet(self.parent().styleSheet() if self.parent() else "")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Add DayMentor Task", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ff66;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Task Title *", self))
        self.txt_title = QLineEdit(self)
        self.txt_title.setPlaceholderText("e.g. Physics Revision")
        layout.addWidget(self.txt_title)

        layout.addWidget(QLabel("Priority", self))
        self.cmb_priority = QComboBox(self)
        self.cmb_priority.addItems(["low", "medium", "high"])
        self.cmb_priority.setCurrentText("medium")
        layout.addWidget(self.cmb_priority)

        layout.addWidget(QLabel("Due Date (Optional)", self))
        self.dt_deadline = QDateEdit(self)
        self.dt_deadline.setCalendarPopup(True)
        self.dt_deadline.setDate(QDate.currentDate().addDays(1))
        layout.addWidget(self.dt_deadline)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Preview Action", self)
        btn_ok.setStyleSheet("background-color: #00ff66; color: black; font-weight: bold;")
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def validate_and_accept(self):
        if not self.txt_title.text().strip():
            QMessageBox.warning(self, "Required Field", "Please enter a task title.")
            return
        self.accept()

    def get_intent(self) -> JarvisEcosystemIntent:
        d = self.dt_deadline.date()
        date_str = f"{d.year():04d}-{d.month():02d}-{d.day():02d}"
        title = self.txt_title.text().strip()
        priority = self.cmb_priority.currentText()
        return JarvisEcosystemIntent(
            command_id="action.daymentor.create_task",
            confidence=1.0,
            parameters={
                "title": title,
                "priority": priority,
                "deadline": date_str,
            },
            requires_confirmation=True,
            summary=f"Create DayMentor Task: {title} (Due {date_str})",
        )


class CricketMatchDialog(QDialog):
    """Cricket Match Form Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Cricket Match")
        self.setFixedSize(380, 310)
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Create Cricket Match", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffaa00;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Team A *", self))
        self.txt_team_a = QLineEdit(self)
        self.txt_team_a.setPlaceholderText("e.g. India")
        layout.addWidget(self.txt_team_a)

        layout.addWidget(QLabel("Team B *", self))
        self.txt_team_b = QLineEdit(self)
        self.txt_team_b.setPlaceholderText("e.g. Australia")
        layout.addWidget(self.txt_team_b)

        grid = QGridLayout()
        grid.addWidget(QLabel("Format", self), 0, 0)
        grid.addWidget(QLabel("Overs", self), 0, 1)

        self.cmb_format = QComboBox(self)
        self.cmb_format.addItems(["T20", "ODI", "Test", "Custom"])
        self.cmb_format.currentTextChanged.connect(self.on_format_changed)
        grid.addWidget(self.cmb_format, 1, 0)

        self.spn_overs = QSpinBox(self)
        self.spn_overs.setRange(1, 100)
        self.spn_overs.setValue(20)
        grid.addWidget(self.spn_overs, 1, 1)
        layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Preview Match", self)
        btn_ok.setStyleSheet("background-color: #ffaa00; color: black; font-weight: bold;")
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def on_format_changed(self, fmt: str):
        if fmt == "T20":
            self.spn_overs.setValue(20)
        elif fmt == "ODI":
            self.spn_overs.setValue(50)
        elif fmt == "Test":
            self.spn_overs.setValue(90)

    def validate_and_accept(self):
        if not self.txt_team_a.text().strip() or not self.txt_team_b.text().strip():
            QMessageBox.warning(self, "Required Fields", "Please enter both Team A and Team B.")
            return
        self.accept()

    def get_intent(self) -> JarvisEcosystemIntent:
        team_a = self.txt_team_a.text().strip()
        team_b = self.txt_team_b.text().strip()
        fmt = self.cmb_format.currentText()
        overs = self.spn_overs.value()
        return JarvisEcosystemIntent(
            command_id="action.cricket.create_match",
            confidence=1.0,
            parameters={
                "team_a": team_a,
                "team_b": team_b,
                "match_type": fmt,
                "overs": overs,
            },
            requires_confirmation=True,
            summary=f"Create Cricket Match: {team_a} vs {team_b} ({fmt})",
        )


class HackathonSimulationDialog(QDialog):
    """Hackathon Simulation Form Dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Start Hackathon Simulation")
        self.setFixedSize(400, 270)
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("Start Hackathon Simulation", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #aa66ff;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Challenge Problem Statement", self))
        self.cmb_problem = QComboBox(self)
        for prob in HACKATHON_PROBLEMS:
            self.cmb_problem.addItem(prob["title"], prob["id"])
        layout.addWidget(self.cmb_problem)

        layout.addWidget(QLabel("Difficulty", self))
        self.cmb_difficulty = QComboBox(self)
        self.cmb_difficulty.addItems(["easy", "medium", "hard"])
        self.cmb_difficulty.setCurrentText("medium")
        layout.addWidget(self.cmb_difficulty)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Preview Simulation", self)
        btn_ok.setStyleSheet("background-color: #aa66ff; color: white; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def get_intent(self) -> JarvisEcosystemIntent:
        prob_id = self.cmb_problem.currentData()
        prob_title = self.cmb_problem.currentText()
        diff = self.cmb_difficulty.currentText()
        return JarvisEcosystemIntent(
            command_id="action.hackathon.start_simulation",
            confidence=1.0,
            parameters={
                "problem_id": prob_id,
                "problem_title": prob_title,
                "difficulty": diff,
            },
            requires_confirmation=True,
            summary=f"Start Hackathon Simulation: {prob_title} ({diff})",
        )


class ActionConfirmationDialog(QDialog):
    """Generic Confirmation Dialog enforcing preview-before-write security."""

    def __init__(self, intent: JarvisEcosystemIntent, parent=None):
        super().__init__(parent)
        self.intent = intent
        self.setWindowTitle("Confirm Ecosystem Action")
        self.setFixedSize(420, 260)
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Review & Confirm Action", self)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ff66;")
        layout.addWidget(title)

        box = QFrame(self)
        box.setStyleSheet("background-color: #242424; border: 1px solid #3d3d3d; border-radius: 6px;")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(6)

        cmd_badge = QLabel(f"COMMAND: {self.intent.command_id}", box)
        cmd_badge.setStyleSheet("color: #888888; font-family: monospace; font-size: 10px;")
        box_layout.addWidget(cmd_badge)

        summary = QLabel(self.intent.summary, box)
        summary.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        summary.setWordWrap(True)
        box_layout.addWidget(summary)

        # Parameters details
        params_str = "\n".join([f"• {k}: {v}" for k, v in self.intent.parameters.items() if v])
        params_lbl = QLabel(params_str, box)
        params_lbl.setStyleSheet("color: #cccccc; font-size: 11px; margin-top: 4px;")
        box_layout.addWidget(params_lbl)

        layout.addWidget(box)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("Confirm & Execute", self)
        btn_confirm.setStyleSheet("background-color: #00ff66; color: #121212; font-weight: bold; padding: 6px 14px;")
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)


# ─── Main Ecosystem Action Drawer Widget ───────────────────────────────────────
class EcosystemDrawer(QWidget):
    """PyFlare Desktop Ecosystem Action Drawer."""

    action_executed = Signal(object)  # Emits ExecutionResult

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EcosystemDrawer")
        self.client = get_ecosystem_client()
        self.executor = EcosystemExecutor(self.client)

        self.setup_ui()
        self.refresh_account_state()
        self.load_recent_activity()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scrollable area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: #1a1a1a;")

        container = QWidget()
        container.setStyleSheet("background-color: #1a1a1a;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── 1. Header & Account Status ──
        self.account_card = QFrame(container)
        self.account_card.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 8px;")
        acc_layout = QVBoxLayout(self.account_card)
        acc_layout.setContentsMargins(14, 12, 14, 12)
        acc_layout.setSpacing(8)

        acc_header = QHBoxLayout()
        title_lbl = QLabel("Aachman Ecosystem", self.account_card)
        title_lbl.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 14px;")
        acc_header.addWidget(title_lbl)

        self.status_dot = QLabel("● Connected", self.account_card)
        self.status_dot.setStyleSheet("color: #00ff66; font-size: 11px; font-weight: bold;")
        acc_header.addWidget(self.status_dot, alignment=Qt.AlignRight)
        acc_layout.addLayout(acc_header)

        self.lbl_email = QLabel("user@example.com", self.account_card)
        self.lbl_email.setStyleSheet("color: #ffffff; font-size: 12px;")
        acc_layout.addWidget(self.lbl_email)

        self.btn_auth_action = QPushButton("Sign In", self.account_card)
        self.btn_auth_action.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        self.btn_auth_action.clicked.connect(self.toggle_auth)
        acc_layout.addWidget(self.btn_auth_action)

        layout.addWidget(self.account_card)

        # ── 2. Quick Actions ──
        actions_header = QLabel("Quick Actions", container)
        actions_header.setStyleSheet("color: #8c8c8c; font-size: 12px; font-weight: bold; text-transform: uppercase;")
        layout.addWidget(actions_header)

        actions_grid = QVBoxLayout()
        actions_grid.setSpacing(6)

        # Task Action
        btn_task = QPushButton("+ Add DayMentor Task", container)
        btn_task.setStyleSheet("background-color: #1e2923; border: 1px solid #00ff66; color: #00ff66; font-weight: 600; padding: 8px 12px; border-radius: 6px; text-align: left; font-size: 12px;")
        btn_task.clicked.connect(self.trigger_daymentor_task)
        actions_grid.addWidget(btn_task)

        # Cricket Action
        btn_cricket = QPushButton("+ Create Cricket Match", container)
        btn_cricket.setStyleSheet("background-color: #29241e; border: 1px solid #ffaa00; color: #ffaa00; font-weight: 600; padding: 8px 12px; border-radius: 6px; text-align: left; font-size: 12px;")
        btn_cricket.clicked.connect(self.trigger_cricket_match)
        actions_grid.addWidget(btn_cricket)

        # Hackathon Action
        btn_hack = QPushButton("+ Start Hackathon Simulation", container)
        btn_hack.setStyleSheet("background-color: #241e29; border: 1px solid #aa66ff; color: #aa66ff; font-weight: 600; padding: 8px 12px; border-radius: 6px; text-align: left; font-size: 12px;")
        btn_hack.clicked.connect(self.trigger_hackathon_simulation)
        actions_grid.addWidget(btn_hack)

        layout.addLayout(actions_grid)

        # ── 3. Your Connected Apps ──
        apps_header = QLabel("Connected Ecosystem Apps", container)
        apps_header.setStyleSheet("color: #8c8c8c; font-size: 12px; font-weight: bold; text-transform: uppercase;")
        layout.addWidget(apps_header)

        apps_list = [
            ("Aachman Hub", "Central portal, projects & achievements", "app.open.aachman_hub"),
            ("DayMentor", "Student routines, tasks & study focus", "app.open.daymentor"),
            ("Cricket Scorer", "Match controller & live scorecards", "app.open.cricket_scorer"),
            ("Hackathon Simulator", "Product strategy simulation & pitch engine", "app.open.hackathon_simulator"),
        ]

        for app_name, app_desc, cmd_id in apps_list:
            app_card = QFrame(container)
            app_card.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
            ac_lay = QHBoxLayout(app_card)
            ac_lay.setContentsMargins(12, 8, 12, 8)

            info_lay = QVBoxLayout()
            info_lay.setSpacing(2)
            lbl_n = QLabel(app_name, app_card)
            lbl_n.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
            lbl_d = QLabel(app_desc, app_card)
            lbl_d.setStyleSheet("color: #888888; font-size: 10px;")
            info_lay.addWidget(lbl_n)
            info_lay.addWidget(lbl_d)
            ac_lay.addLayout(info_lay, 1)

            btn_open = QPushButton("Open ↗", app_card)
            btn_open.setStyleSheet("background-color: #2d2d2d; color: #00ff66; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold;")
            btn_open.clicked.connect(lambda ch=False, cid=cmd_id: self.launch_app(cid))
            ac_lay.addWidget(btn_open)

            layout.addWidget(app_card)

        # ── 4. Recent Ecosystem Activity ──
        act_header_lay = QHBoxLayout()
        act_lbl = QLabel("Recent Activity", container)
        act_lbl.setStyleSheet("color: #8c8c8c; font-size: 12px; font-weight: bold; text-transform: uppercase;")
        act_header_lay.addWidget(act_lbl)

        self.btn_refresh_act = QPushButton("↻", container)
        self.btn_refresh_act.setToolTip("Refresh Activity")
        self.btn_refresh_act.setStyleSheet("background-color: transparent; color: #888888; border: none; font-size: 14px; font-weight: bold;")
        self.btn_refresh_act.clicked.connect(self.load_recent_activity)
        act_header_lay.addWidget(self.btn_refresh_act, alignment=Qt.AlignRight)
        layout.addLayout(act_header_lay)

        self.activity_container = QVBoxLayout()
        self.activity_container.setSpacing(6)
        layout.addLayout(self.activity_container)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def refresh_account_state(self):
        """Update account header UI according to current auth state."""
        if self.client.is_authenticated:
            self.status_dot.setText("● Connected")
            self.status_dot.setStyleSheet("color: #00ff66; font-size: 11px; font-weight: bold;")
            self.lbl_email.setText(self.client.user_email or "Aachman User")
            self.btn_auth_action.setText("Sign Out")
            self.btn_auth_action.setStyleSheet("background-color: #2d2d2d; color: #ff6666; border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        else:
            self.status_dot.setText("● Not Connected")
            self.status_dot.setStyleSheet("color: #ffaa00; font-size: 11px; font-weight: bold;")
            self.lbl_email.setText("Connect your Aachman Account to sync.")
            self.btn_auth_action.setText("Sign In")
            self.btn_auth_action.setStyleSheet("background-color: #00ff66; color: #121212; font-weight: bold; border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px;")

    def toggle_auth(self):
        """Sign in or sign out depending on current state."""
        if self.client.is_authenticated:
            reply = QMessageBox.question(
                self,
                "Sign Out",
                "Are you sure you want to sign out from your Aachman Account?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.client.sign_out()
                self.refresh_account_state()
                self.load_recent_activity()
        else:
            dlg = EcosystemLoginDialog(self.client, self)
            if dlg.exec() == QDialog.Accepted:
                self.refresh_account_state()
                self.load_recent_activity()

    def launch_app(self, command_id: str):
        """Launch allowlisted web app safely."""
        intent = JarvisEcosystemIntent(
            command_id=command_id,
            confidence=1.0,
            parameters={},
            requires_confirmation=False,
            summary=f"Launch {command_id}",
        )
        res = self.executor.execute_intent(intent, confirm=True)
        self.action_executed.emit(res)

    def trigger_daymentor_task(self):
        if not self.client.is_authenticated:
            QMessageBox.information(self, "Sign In Required", "Please sign in to create a DayMentor task.")
            self.toggle_auth()
            return

        dlg = DayMentorTaskDialog(self)
        if dlg.exec() == QDialog.Accepted:
            intent = dlg.get_intent()
            self._confirm_and_dispatch(intent)

    def trigger_cricket_match(self):
        if not self.client.is_authenticated:
            QMessageBox.information(self, "Sign In Required", "Please sign in to create a Cricket match.")
            self.toggle_auth()
            return

        dlg = CricketMatchDialog(self)
        if dlg.exec() == QDialog.Accepted:
            intent = dlg.get_intent()
            self._confirm_and_dispatch(intent)

    def trigger_hackathon_simulation(self):
        if not self.client.is_authenticated:
            QMessageBox.information(self, "Sign In Required", "Please sign in to start a simulation.")
            self.toggle_auth()
            return

        dlg = HackathonSimulationDialog(self)
        if dlg.exec() == QDialog.Accepted:
            intent = dlg.get_intent()
            self._confirm_and_dispatch(intent)

    def _confirm_and_dispatch(self, intent: JarvisEcosystemIntent):
        """Enforces confirmation preview dialog before executing write."""
        conf_dlg = ActionConfirmationDialog(intent, self)
        if conf_dlg.exec() != QDialog.Accepted:
            log.info(f"User cancelled action: {intent.command_id}")
            return

        # Execute in background thread
        worker = EcosystemWorker(self.executor.execute_intent, intent, confirm=True)

        def on_result(res: ExecutionResult):
            self.action_executed.emit(res)
            if res.status == "success":
                QMessageBox.information(self, "Action Success", res.message)
                self.load_recent_activity()
            else:
                QMessageBox.warning(self, "Action Failed", res.message)

        def on_error(err_msg: str):
            QMessageBox.warning(self, "Execution Error", f"Network error: {err_msg}")

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def load_recent_activity(self):
        """Asynchronously load recent ecosystem activity."""
        # Clear existing items
        while self.activity_container.count():
            item = self.activity_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.client.is_authenticated:
            empty_lbl = QLabel("Sign in to see your recent ecosystem activity.", self)
            empty_lbl.setStyleSheet("color: #666666; font-size: 11px; font-style: italic;")
            self.activity_container.addWidget(empty_lbl)
            return

        loading_lbl = QLabel("Loading activity...", self)
        loading_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        self.activity_container.addWidget(loading_lbl)

        worker = EcosystemWorker(self.client.fetch_recent_activity, limit=5)

        def on_result(activities: List[Dict[str, Any]]):
            while self.activity_container.count():
                item = self.activity_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not activities:
                empty_lbl = QLabel("No recent ecosystem activity recorded yet.", self)
                empty_lbl.setStyleSheet("color: #666666; font-size: 11px; font-style: italic;")
                self.activity_container.addWidget(empty_lbl)
                return

            for act in activities:
                card = QFrame(self)
                card.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
                card_lay = QHBoxLayout(card)
                card_lay.setContentsMargins(10, 8, 10, 8)

                text_lay = QVBoxLayout()
                text_lay.setSpacing(2)

                app_id = act.get("app_id", "hub")
                title = act.get("title", "Ecosystem Action")
                subtitle = act.get("subtitle", "")

                t_lbl = QLabel(f"{title}", card)
                t_lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 600;")
                s_lbl = QLabel(f"{app_id.replace('_', ' ').title()} · {subtitle}", card)
                s_lbl.setStyleSheet("color: #888888; font-size: 10px;")

                text_lay.addWidget(t_lbl)
                text_lay.addWidget(s_lbl)
                card_lay.addLayout(text_lay, 1)

                deep_link = act.get("deep_link")
                if deep_link:
                    btn_view = QPushButton("View", card)
                    btn_view.setStyleSheet("background-color: #2d2d2d; color: #00ff66; border: 1px solid #3d3d3d; border-radius: 4px; padding: 2px 6px; font-size: 10px;")
                    btn_view.clicked.connect(lambda ch=False, dl=deep_link: self.open_verified_link(dl))
                    card_lay.addWidget(btn_view)

                self.activity_container.addWidget(card)

        def on_error(err_str: str):
            while self.activity_container.count():
                item = self.activity_container.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            err_lbl = QLabel("Could not load activity (Offline mode).", self)
            err_lbl.setStyleSheet("color: #ffaa00; font-size: 11px;")
            self.activity_container.addWidget(err_lbl)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)

    def open_verified_link(self, url: str):
        """Open link only if it belongs to allowlisted ecosystem domains."""
        if any(url.startswith(base) for base in ECOSYSTEM_URLS.values()):
            webbrowser.open(url)
        else:
            log.warning(f"Blocked untrusted activity URL: {url}")
