from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QFrame
from desktop_ui.state.app_state import app_state
from desktop_ui.state.event_bus import event_bus


class Topbar(QWidget):
    search_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Topbar")
        self.setFixedHeight(48)
        
        self.setStyleSheet("""
            QWidget#Topbar {
                background-color: #212121;
                border-bottom: 1px solid #2d2d2d;
            }
            QLabel {
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QPushButton#SearchBtn {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding: 4px 16px;
                text-align: left;
                min-width: 320px;
            }
            QPushButton#SearchBtn:hover {
                background-color: #3b3b3b;
                border-color: #00ff66;
                color: #ffffff;
            }
        """)
        
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # 1. App logo & Title
        title_label = QLabel("AppSuite Jarvis", self)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #00ff66;")
        layout.addWidget(title_label)

        # 2. Active project badge
        self.project_label = QLabel(f"[{app_state.active_project}]", self)
        self.project_label.setStyleSheet("font-weight: 600; color: #ffffff;")
        layout.addWidget(self.project_label)

        # Spacer
        layout.addSpacing(16)

        # 3. Global search button
        self.search_btn = QPushButton("Search Workspace Everywhere (Ctrl+P)", self)
        self.search_btn.setObjectName("SearchBtn")
        self.search_btn.clicked.connect(self.search_clicked.emit)
        layout.addWidget(self.search_btn)
        
        layout.addStretch()

        # 4. Active provider
        provider_label = QLabel("Active Provider: Gemini 2.5 Flash / NIM", self)
        provider_label.setStyleSheet("color: #8c8c8c;")
        layout.addWidget(provider_label)

        # 5. Status indicator
        self.status_label = QLabel("STATUS: IDLE", self)
        self.status_label.setStyleSheet("font-weight: bold; color: #00ff66;")
        layout.addWidget(self.status_label)

        # Connect event subscriptions
        event_bus.subscribe("JOB_STARTED", self.on_job_start)
        event_bus.subscribe("JOB_UPDATED", self.on_job_update)
        event_bus.subscribe("JOB_FINISHED", self.on_job_finish)
        event_bus.subscribe("PROJECT_CHANGED", self.on_project_changed)

    def on_job_start(self, data):
        prompt = data.get("prompt", "")
        self.status_label.setText(f"STATUS: RUNNING ({prompt[:12]}...)")
        self.status_label.setStyleSheet("font-weight: bold; color: #ffcc00;")

    def on_job_update(self, data):
        stage = data.get("stage", "EXECUTING").upper()
        self.status_label.setText(f"STATUS: {stage}")
        self.status_label.setStyleSheet("font-weight: bold; color: #ffcc00;")

    def on_job_finish(self, data):
        self.status_label.setText("STATUS: IDLE")
        self.status_label.setStyleSheet("font-weight: bold; color: #00ff66;")

    def on_project_changed(self, data):
        project = data.get("project", "")
        self.project_label.setText(f"[{project}]")
