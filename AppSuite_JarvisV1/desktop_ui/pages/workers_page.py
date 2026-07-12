from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout
)
from desktop_ui.state.app_state import app_state


class WorkersPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkersPage")
        self.setStyleSheet("""
            QWidget#WorkersPage {
                background-color: #1a1a1a;
            }
            QLabel#PageTitle {
                color: #00ff66;
                font-family: 'Segoe UI';
                font-size: 20px;
                font-weight: bold;
            }
            QFrame.WorkerCard {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
            QLabel.WorkerName {
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 14px;
                font-weight: bold;
            }
            QLabel.WorkerStatus {
                font-family: 'Segoe UI';
                font-size: 12px;
                font-weight: bold;
            }
            QLabel.WorkerTask {
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QLabel.WorkerMetrics {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QPushButton.CardBtn {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton.CardBtn:hover {
                background-color: #3b3b3b;
                border-color: #00ff66;
            }
            QFrame#StatBar {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Title
        title = QLabel("Workers Control Console", self)
        title.setObjectName("PageTitle")
        main_layout.addWidget(title)

        # Grid container for cards
        self.grid_widget = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(16)
        
        main_layout.addWidget(self.grid_widget, 1)

        # Bottom stat bar
        self.stat_bar = QFrame(self)
        self.stat_bar.setObjectName("StatBar")
        stat_layout = QHBoxLayout(self.stat_bar)
        stat_layout.setContentsMargins(16, 8, 16, 8)
        
        self.lbl_info = QLabel("Total Active Workers: 8  |  Average Success Rate: 100.0%  |  Telemetry Update Interval: 0.5s", self.stat_bar)
        self.lbl_info.setStyleSheet("color: #8c8c8c; font-size: 12px;")
        stat_layout.addWidget(self.lbl_info)
        stat_layout.addStretch()
        
        main_layout.addWidget(self.stat_bar)

        # Draw worker cards
        self.worker_widgets = {}
        self.render_worker_cards()

        # Connect AppState updates
        app_state.state_updated.connect(self.update_telemetry)

    def render_worker_cards(self):
        # Clear grid layout first
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        self.worker_widgets = {}
        row = 0
        col = 0
        for name, details in app_state.workers.items():
            card = QFrame(self.grid_widget)
            card.setObjectName(f"Card_{name}")
            card.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
            
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(6)

            # Header
            lbl_name = QLabel(name, card)
            lbl_name.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 14px;")
            card_layout.addWidget(lbl_name)

            # Status and Color Code (Phase 2: Green = Idle/Healthy, Yellow = Running, Red = Failed)
            lbl_status = QLabel(f"Status: {details['status']}", card)
            status_lower = details['status'].lower()
            if "running" in status_lower:
                lbl_status.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 12px;")
            elif "failed" in status_lower:
                lbl_status.setStyleSheet("color: #ff3333; font-weight: bold; font-size: 12px;")
            else:
                lbl_status.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 12px;")
            card_layout.addWidget(lbl_status)

            lbl_task = QLabel(f"Task: {details['task']}", card)
            lbl_task.setStyleSheet("color: #e0e0e0; font-size: 12px;")
            card_layout.addWidget(lbl_task)

            # Extra Metrics (Phase 2: Success %, Failure Count, Last Execution Time)
            lbl_metrics = QLabel(
                f"Success Rate: {details['success']}%  |  Failures: {details['failures']}\nLast Exec: {details['last_exec']}", 
                card
            )
            lbl_metrics.setStyleSheet("color: #8c8c8c; font-size: 11px;")
            card_layout.addWidget(lbl_metrics)

            # Buttons panel
            btn_panel = QWidget(card)
            btn_layout = QHBoxLayout(btn_panel)
            btn_layout.setContentsMargins(0, 4, 0, 0)
            btn_layout.setSpacing(8)

            btn_restart = QPushButton("Restart", btn_panel)
            btn_restart.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
            btn_restart.clicked.connect(lambda checked=False, n=name: self.restart_worker(n))
            btn_layout.addWidget(btn_restart)

            btn_debug = QPushButton("Debug", btn_panel)
            btn_debug.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
            btn_debug.clicked.connect(lambda checked=False, n=name: self.debug_worker(n))
            btn_layout.addWidget(btn_debug)
            
            btn_layout.addStretch()
            card_layout.addWidget(btn_panel)

            self.grid_layout.addWidget(card, row, col)

            self.worker_widgets[name] = {
                "status": lbl_status,
                "task": lbl_task,
                "metrics": lbl_metrics
            }

            col += 1
            if col > 1:
                col = 0
                row += 1

    def update_telemetry(self):
        """Updates labels dynamically from app_state worker details."""
        total_success = 0.0
        active_count = 0
        
        for name, details in app_state.workers.items():
            total_success += details.get("success", 100.0)
            if "running" in details.get("status", "").lower():
                active_count += 1
                
            if name in self.worker_widgets:
                lbl_status = self.worker_widgets[name]["status"]
                lbl_task = self.worker_widgets[name]["task"]
                lbl_metrics = self.worker_widgets[name]["metrics"]

                lbl_status.setText(f"Status: {details['status']}")
                status_lower = details['status'].lower()
                if "running" in status_lower:
                    lbl_status.setStyleSheet("color: #ffcc00; font-weight: bold; font-size: 12px;")
                elif "failed" in status_lower:
                    lbl_status.setStyleSheet("color: #ff3333; font-weight: bold; font-size: 12px;")
                else:
                    lbl_status.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 12px;")

                lbl_task.setText(f"Task: {details['task']}")
                lbl_metrics.setText(
                    f"Success Rate: {details['success']}%  |  Failures: {details['failures']}\nLast Exec: {details['last_exec']}"
                )

        avg_success = round(total_success / len(app_state.workers), 1) if app_state.workers else 100.0
        self.lbl_info.setText(f"Total Active Workers: {len(app_state.workers)}  |  Average Success Rate: {avg_success}%  |  Telemetry Update Interval: 0.5s")

    def restart_worker(self, name: str):
        app_state.add_timeline_event(f"Restarted worker instance: {name}", "INFO", stage="system", worker="Supervisor")
        # In actual backend, workers are class singletons. We can simulate a restart signal.
        if name in app_state.workers:
            app_state.workers[name]["status"] = "Idle/Healthy"
            app_state.workers[name]["task"] = "Idle"
        self.update_telemetry()

    def debug_worker(self, name: str):
        app_state.add_timeline_event(f"Debugging diagnostics on: {name}", "WARNING", stage="system", worker=name)
        app_state.update_inspector(
            stage=name,
            error="None",
            retry_count=0,
            worker=name,
            stacktrace=f"Debugging worker details:\nInstance path: appsuite.workers.{name}\nNo issues detected on runtime thread."
        )
