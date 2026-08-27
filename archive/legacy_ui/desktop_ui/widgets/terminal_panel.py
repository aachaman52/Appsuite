import os
import random
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout
)
from desktop_ui.state.app_state import app_state
from desktop_ui.state.event_bus import event_bus


class TerminalPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TerminalPanel")
        self.setFixedHeight(220)
        
        self.setStyleSheet("""
            QWidget#TerminalPanel {
                background-color: #1a1a1a;
                border-top: 1px solid #2d2d2d;
            }
            QTabWidget::pane {
                border: none;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #8c8c8c;
                padding: 6px 16px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a1a;
                color: #00ff66;
                border-bottom: 1px solid #1a1a1a;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QTextEdit, QTableWidget {
                background-color: #151515;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
                color: #e0e0e0;
                font-family: 'Consolas';
                font-size: 11px;
                padding: 4px;
            }
            QTableWidget {
                gridline-color: #2d2d2d;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #8c8c8c;
                border: none;
                border-bottom: 1px solid #2d2d2d;
                padding: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QTextEdit#LogTxt {
                color: #c8c8c8;
            }
            QTextEdit#ResTxt {
                color: #00ff66;
            }
        """)

        self._log_file_path = None
        self._log_file_offset = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(0)

        # Tab Widget
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab 1: Live Logs (reads from appsuite.log)
        self.log_txt = QTextEdit(self)
        self.log_txt.setObjectName("LogTxt")
        self.log_txt.setReadOnly(True)
        self.tabs.addTab(self.log_txt, "Live Logs")

        # Tab 2: Event Bus logs
        self.event_txt = QTextEdit(self)
        self.event_txt.setReadOnly(True)
        self.tabs.addTab(self.event_txt, "Event Bus")

        # Tab 3: Job Queue (Phase 6: Job ID, Prompt, Status, Progress, Runtime, Actions)
        self.queue_table = QTableWidget(self)
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels(["Job ID", "Prompt", "Status", "Progress", "Runtime", "Actions"])
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.queue_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tabs.addTab(self.queue_table, "Job Queue")

        # Tab 4: Resource Monitor (Phase 1 CPU/RAM/Disk metrics)
        self.res_txt = QTextEdit(self)
        self.res_txt.setObjectName("ResTxt")
        self.res_txt.setReadOnly(True)
        self.tabs.addTab(self.res_txt, "Resource Monitor")

        # Populate initially
        self.log_txt.append("[System Initialization] AppSuite Live Log Monitor...")
        self.event_txt.append("PUB/SUB Event Log initialized.")
        
        # Setup resource monitoring updates with QTimer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.poll_updates)
        self.update_timer.start(500)  # Telemetry interval (500ms)
        self.poll_updates()

        # Subscribe to events
        event_bus.subscribe("JOB_FINISHED", self.on_job_event)
        event_bus.subscribe("TIMELINE_UPDATED", self.on_timeline_event)

    def on_job_event(self, data):
        self.event_txt.append(f"PUBLISH: JOB_FINISHED -> {data}")
        self.refresh_queue()

    def on_timeline_event(self, data):
        self.event_txt.append(f"PUBLISH: TIMELINE_UPDATED -> {data}")

    def poll_updates(self):
        """Poll resources, read logs, and refresh job queue."""
        self.update_resource_logs()
        self.read_live_logs()
        self.refresh_queue()

    def read_live_logs(self):
        """Reads new lines from real appsuite.log and appends them to text widget."""
        if not app_state.ctx:
            return

        if self._log_file_path is None:
            self._log_file_path = app_state.ctx.config.abs_path("log_dir") / "appsuite.log"
            if not self._log_file_path.exists():
                return
            self._log_file_offset = 0

        if not self._log_file_path.exists():
            return

        try:
            file_size = os.path.getsize(self._log_file_path)
            if file_size < self._log_file_offset:
                # Log file rotated/truncated
                self._log_file_offset = 0
                self.log_txt.clear()

            if file_size > self._log_file_offset:
                with open(self._log_file_path, "r", encoding="utf-8") as f:
                    f.seek(self._log_file_offset)
                    new_text = f.read()
                    self._log_file_offset = f.tell()
                    
                    if new_text:
                        self.log_txt.append(new_text.strip())
        except Exception:
            pass

    def refresh_queue(self):
        """Refresh Job Manager queue with pause, resume, and cancel actions."""
        self.queue_table.blockSignals(True)
        self.queue_table.setRowCount(0)
        
        for idx, j in enumerate(app_state.jobs):
            self.queue_table.insertRow(idx)
            
            # Populate columns
            self.queue_table.setItem(idx, 0, QTableWidgetItem(j["id"][:8]))
            self.queue_table.setItem(idx, 1, QTableWidgetItem(j["prompt"]))
            self.queue_table.setItem(idx, 2, QTableWidgetItem(j["status"].upper()))
            
            progress = j.get("progress", 0.0)
            self.queue_table.setItem(idx, 3, QTableWidgetItem(f"{progress:.1f}%"))
            self.queue_table.setItem(idx, 4, QTableWidgetItem(j["time"]))
            
            # Actions cell (Pause, Resume, Cancel)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(4)
            
            btn_style = "border: 1px solid #3d3d3d; border-radius: 3px; font-size: 9px; padding: 2px 6px; color: white;"
            
            btn_pause = QPushButton("Pause", action_widget)
            btn_pause.setStyleSheet(btn_style + "background-color: #2b2b2b;")
            btn_pause.clicked.connect(lambda checked=False, job_id=j["id"]: app_state.pause_job(job_id))
            
            btn_resume = QPushButton("Resume", action_widget)
            btn_resume.setStyleSheet(btn_style + "background-color: #2b2b2b;")
            btn_resume.clicked.connect(lambda checked=False, job_id=j["id"]: app_state.resume_job(job_id))
            
            btn_cancel = QPushButton("Cancel", action_widget)
            btn_cancel.setStyleSheet(btn_style + "background-color: #c9302c;")
            btn_cancel.clicked.connect(lambda checked=False, job_id=j["id"]: app_state.cancel_job(job_id))
            
            action_layout.addWidget(btn_pause)
            action_layout.addWidget(btn_resume)
            action_layout.addWidget(btn_cancel)
            action_layout.addStretch()
            
            self.queue_table.setCellWidget(idx, 5, action_widget)
            
        self.queue_table.blockSignals(False)

    def update_resource_logs(self):
        """Displays real telemetry output in resource tab."""
        if not app_state.ctx:
            return
            
        res = app_state.ctx.hardware.resources()
        cpu = res.get("cpu_percent") or 0.0
        ram = res.get("ram_percent") or 0.0
        disk_free = res.get("disk", {}).get("free_gb") or 0.0
        disk_total = res.get("disk", {}).get("total_gb") or 0.0
        
        gpu_stat = res.get("gpu", {})
        gpu_avail = gpu_stat.get("available", False)
        
        net_stat = res.get("network", {})
        net_sent = net_stat.get("sent_kbps", 0.0)
        net_recv = net_stat.get("recv_kbps", 0.0)

        self.res_txt.clear()
        self.res_txt.append("--- AppSuite Real-Time Telemetry Gate ---")
        self.res_txt.append(f"CPU Load: {cpu}%")
        self.res_txt.append(f"RAM Utilization: {ram}%")
        self.res_txt.append(f"Disk Space: {disk_free} GB Free / {disk_total} GB Total")
        self.res_txt.append(f"GPU Availability: {'ACTIVE' if gpu_avail else 'INACTIVE'} (VRAM Used: {gpu_stat.get('vram_used', 0)}MB)")
        self.res_txt.append(f"Network IO: Sent {net_sent:.1f} KB/s  |  Received {net_recv:.1f} KB/s")
        self.res_txt.append(f"Uptime: {app_state.ctx.hardware.uptime:.1f}s")
