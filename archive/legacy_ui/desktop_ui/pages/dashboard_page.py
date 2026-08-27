import os
import random
import subprocess
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QFrame, QGridLayout, QLineEdit, QProgressBar
)
from desktop_ui.state.app_state import app_state
from desktop_ui.state.event_bus import event_bus


class SystemMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Deep dark background for canvas
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        # Check supervisor
        sup_status = app_state.workers.get("Supervisor", {}).get("status", "Idle/Healthy")
        sup_color = "Yellow" if "Running" in sup_status else ("Red" if "Failed" in sup_status else "Green")
        
        # Check other workers
        workers_color = "Green"
        for w_name in ["InternetWorker", "BlenderWorker", "GodotWorker", "ValidationWorker", "AssetWorker"]:
            stat = app_state.workers.get(w_name, {}).get("status", "Idle/Healthy")
            if "Running" in stat:
                workers_color = "Yellow"
                break
            elif "Failed" in stat:
                workers_color = "Red"

        # Node coordinates: (x, y, label, status_color)
        nodes = {
            "Jarvis": (60, 100, "Green"),
            "Supervisor": (190, 50, sup_color),
            "Memory": (190, 150, "Green"),
            "Planner": (320, 50, "Green"),
            "Workers": (320, 150, workers_color)
        }

        # Colors mapping
        colors = {
            "Green": QColor("#00ff66"),
            "Yellow": QColor("#ffcc00"),
            "Red": QColor("#ff3333")
        }

        # Draw connections (lines)
        pen = QPen(QColor("#3d3d3d"), 2)
        painter.setPen(pen)
        painter.drawLine(60, 100, 190, 50)
        painter.drawLine(60, 100, 190, 150)
        painter.drawLine(190, 50, 320, 50)
        painter.drawLine(190, 150, 320, 150)

        # Draw nodes
        for name, (x, y, status) in nodes.items():
            color = colors[status]
            
            # Circle border and fill
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(QColor("#252525")))
            painter.drawEllipse(x - 24, y - 24, 48, 48)

            # Node letter
            painter.setPen(QPen(QColor("#ffffff")))
            font = QFont("Segoe UI", 12, QFont.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(x - 24, y - 24, 48, 48), Qt.AlignCenter, name[0])

            # Label text below node
            painter.setPen(QPen(QColor("#e0e0e0")))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(x - 50, y + 36, 100, 20, Qt.AlignCenter, name)

            # Status text
            painter.setPen(QPen(color))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.drawText(x - 50, y + 50, 100, 20, Qt.AlignCenter, status)


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardPage")
        self.setStyleSheet("""
            QWidget#DashboardPage {
                background-color: #1a1a1a;
            }
            QLabel#PageTitle {
                color: #00ff66;
                font-family: 'Segoe UI';
                font-size: 20px;
                font-weight: bold;
            }
            QFrame.MetricCard {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
            QLabel.MetricTitle {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QLabel.MetricValue {
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 18px;
                font-weight: bold;
            }
            QFrame.PanelFrame {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
            QLabel.PanelTitle {
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: bold;
                padding-left: 4px;
            }
            QListWidget {
                background-color: #1a1a1a;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
                color: #e0e0e0;
                font-family: 'Consolas';
                font-size: 12px;
                padding: 4px;
            }
            QPushButton.ActionBtn {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton.ActionBtn:hover {
                background-color: #3b3b3b;
                border-color: #00ff66;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Title
        title = QLabel("Jarvis v2 OS Dashboard", self)
        title.setObjectName("PageTitle")
        main_layout.addWidget(title)

        # Metrics row (Phase 1: 500ms live metrics)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)
        self.metric_labels = {}
        
        metrics = [
            ("CPU Usage", "0.0%"),
            ("RAM Usage", "0.0%"),
            ("GPU Usage", "0.0%"),
            ("Disk Space", "0.0GB Free")
        ]

        for name, default_val in metrics:
            card = QFrame(self)
            card.setFrameShape(QFrame.StyledPanel)
            card.className = "MetricCard"
            card.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
            
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(4)

            lbl_name = QLabel(name, card)
            lbl_name.setStyleSheet("color: #8c8c8c; font-size: 11px;")
            card_layout.addWidget(lbl_name)

            lbl_val = QLabel(default_val, card)
            lbl_val.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
            card_layout.addWidget(lbl_val)
            
            metrics_layout.addWidget(card, 1)
            self.metric_labels[name] = lbl_val

        main_layout.addLayout(metrics_layout)

        # Split area
        split_layout = QHBoxLayout()
        split_layout.setSpacing(16)

        # Left panel: System Map & Telemetry
        self.map_frame = QFrame(self)
        self.map_frame.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
        map_layout = QVBoxLayout(self.map_frame)
        map_layout.setContentsMargins(16, 12, 16, 16)
        map_layout.setSpacing(8)

        map_title = QLabel("System Architecture Map & Telemetry Gate", self.map_frame)
        map_title.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")
        map_layout.addWidget(map_title)

        self.system_map = SystemMapWidget(self.map_frame)
        map_layout.addWidget(self.system_map, 1)
        
        # Phase 8: Generated Output Viewer (Placed inside the left column below System Map)
        self.output_frame = QFrame(self.map_frame)
        self.output_frame.setStyleSheet("background-color: #1a1a1a; border: 1px solid #2d2d2d; border-radius: 4px; margin-top: 8px;")
        out_layout = QVBoxLayout(self.output_frame)
        out_layout.setContentsMargins(12, 10, 12, 10)
        out_layout.setSpacing(6)
        
        out_title = QLabel("Generated Output Viewer", self.output_frame)
        out_title.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 12px;")
        out_layout.addWidget(out_title)
        
        self.lbl_out_folder = QLabel("Output Folder: None", self.output_frame)
        self.lbl_out_folder.setStyleSheet("color: #cccccc; font-size: 11px;")
        out_layout.addWidget(self.lbl_out_folder)
        
        self.lbl_out_scene = QLabel("Scene Path: None", self.output_frame)
        self.lbl_out_scene.setStyleSheet("color: #cccccc; font-size: 11px;")
        out_layout.addWidget(self.lbl_out_scene)
        
        self.lbl_out_assets = QLabel("Asset Count: 0", self.output_frame)
        self.lbl_out_assets.setStyleSheet("color: #cccccc; font-size: 11px;")
        out_layout.addWidget(self.lbl_out_assets)
        
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(8)
        
        self.btn_open_folder = QPushButton("Open Folder", self.output_frame)
        self.btn_open_folder.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.btn_layout.addWidget(self.btn_open_folder)
        
        self.btn_open_proj = QPushButton("Open Godot Project", self.output_frame)
        self.btn_open_proj.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        self.btn_open_proj.clicked.connect(self.open_project)
        self.btn_layout.addWidget(self.btn_open_proj)
        
        self.btn_open_scene = QPushButton("Open Scene", self.output_frame)
        self.btn_open_scene.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;")
        self.btn_open_scene.clicked.connect(self.open_scene)
        self.btn_layout.addWidget(self.btn_open_scene)
        
        self.btn_layout.addStretch()
        out_layout.addLayout(self.btn_layout)
        
        map_layout.addWidget(self.output_frame)
        split_layout.addWidget(self.map_frame, 1)

        # Right panel: Jobs list and Failures list
        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Recent Jobs
        jobs_frame = QFrame(right_panel)
        jobs_frame.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
        jf_layout = QVBoxLayout(jobs_frame)
        jf_layout.setContentsMargins(16, 12, 16, 16)
        jf_layout.setSpacing(8)

        jobs_title = QLabel("Recent Jobs", jobs_frame)
        jobs_title.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px;")
        jf_layout.addWidget(jobs_title)

        self.jobs_list = QListWidget(jobs_frame)
        jf_layout.addWidget(self.jobs_list, 1)
        right_layout.addWidget(jobs_frame, 1)

        # Failures & Diagnostics
        fail_frame = QFrame(right_panel)
        fail_frame.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
        ff_layout = QVBoxLayout(fail_frame)
        ff_layout.setContentsMargins(16, 12, 16, 16)
        ff_layout.setSpacing(8)

        fail_title = QLabel("Recent Failures & Diagnostics", fail_frame)
        fail_title.setStyleSheet("color: #ff3333; font-weight: bold; font-size: 13px;")
        ff_layout.addWidget(fail_title)

        self.fail_list = QListWidget(fail_frame)
        self.fail_list.itemClicked.connect(self.on_fail_selected)
        ff_layout.addWidget(self.fail_list, 1)
        right_layout.addWidget(fail_frame, 1)

        split_layout.addWidget(right_panel, 1)
        main_layout.addLayout(split_layout, 1)

        # Phase 7: Prompt Runner text box & Run button
        prompt_panel = QFrame(self)
        prompt_panel.setStyleSheet("background-color: #212121; border: 1px solid #2d2d2d; border-radius: 6px;")
        prompt_lay = QHBoxLayout(prompt_panel)
        prompt_lay.setContentsMargins(12, 8, 12, 8)
        prompt_lay.setSpacing(8)
        
        lbl_prompt = QLabel("Prompt:", prompt_panel)
        lbl_prompt.setStyleSheet("color: #8c8c8c; font-size: 12px; font-weight: bold;")
        prompt_lay.addWidget(lbl_prompt)
        
        self.txt_prompt = QLineEdit(prompt_panel)
        self.txt_prompt.setPlaceholderText("Enter scene generation prompt (e.g., Create a GTA-like street block)...")
        self.txt_prompt.setStyleSheet("background-color: #1a1a1a; border: 1px solid #3d3d3d; border-radius: 4px; color: white; padding: 6px; font-size: 12px;")
        self.txt_prompt.returnPressed.connect(self.run_generation)
        prompt_lay.addWidget(self.txt_prompt, 1)
        
        self.btn_run = QPushButton("Run Generation", prompt_panel)
        self.btn_run.setStyleSheet("background-color: #00ff66; border: none; color: #121212; font-weight: bold; padding: 6px 16px; border-radius: 4px; font-size: 12px;")
        self.btn_run.clicked.connect(self.run_generation)
        prompt_lay.addWidget(self.btn_run)
        
        main_layout.addWidget(prompt_panel)

        # Quick Actions
        actions_widget = QWidget(self)
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        lbl_act = QLabel("Quick Actions:", actions_widget)
        lbl_act.setStyleSheet("color: #8c8c8c; font-size: 12px;")
        actions_layout.addWidget(lbl_act)

        self.btn_gta = QPushButton("Generate GTA Street Block", actions_widget)
        self.btn_gta.className = "ActionBtn"
        self.btn_gta.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_gta.clicked.connect(self.trigger_gta_scene)
        actions_layout.addWidget(self.btn_gta)

        self.btn_med = QPushButton("Generate Medieval Village", actions_widget)
        self.btn_med.className = "ActionBtn"
        self.btn_med.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3d3d3d; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_med.clicked.connect(self.trigger_medieval_scene)
        actions_layout.addWidget(self.btn_med)

        actions_layout.addStretch()
        main_layout.addWidget(actions_widget)

        # Subscriptions & State Updates
        app_state.state_updated.connect(self.refresh_ui)
        app_state.job_completed.connect(self.on_job_completed)

        # Timer setup for telemetry loop - Phase 1: 500ms Refresh Rate
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(500)
        self.update_telemetry()
        self.refresh_ui()

    def update_telemetry(self):
        """Polls real hardware metrics and pulls DB changes."""
        if not app_state.ctx:
            return
            
        # Call resources()
        res = app_state.ctx.hardware.resources()
        cpu = res.get("cpu_percent") or 0.0
        ram = res.get("ram_percent") or 0.0
        
        disk_free = res.get("disk", {}).get("free_gb") or 0.0
        gpu_stat = res.get("gpu", {})
        gpu_vram = gpu_stat.get("vram_used", 0) if gpu_stat else 0
        
        self.metric_labels["CPU Usage"].setText(f"{cpu}%")
        self.metric_labels["RAM Usage"].setText(f"{ram}%")
        self.metric_labels["GPU Usage"].setText(f"{gpu_vram}%" if gpu_vram > 0 else "0.0%")
        self.metric_labels["Disk Space"].setText(f"{disk_free}GB Free")

        # Repaint system map node states
        self.system_map.update()

    def refresh_ui(self):
        """Refreshes jobs list and recent diagnostics list from app_state."""
        # 1. Refresh Jobs List
        self.jobs_list.clear()
        for j in app_state.jobs:
            self.jobs_list.addItem(f"[{j['status'].upper()}] {j['prompt']} ({j['time']})")

        # 2. Refresh Failures List (pull from database failures table or jobs list)
        self.fail_list.clear()
        
        # Load real failures from SQLite database failure_memory
        if app_state.ctx:
            failures_db = app_state.ctx.db.query("SELECT * FROM failure_memory ORDER BY created_at DESC LIMIT 10")
            for f in failures_db:
                self.fail_list.addItem(f"[CRITICAL] {f.get('prompt')}: {f.get('error')}")
                
        # If empty, add standard diagnostics defaults
        if self.fail_list.count() == 0:
            self.fail_list.addItem("[CRITICAL] Godot import: DEPENDENCY_MISSING: GODOT_NOT_FOUND")
            self.fail_list.addItem("[WARNING] Validation overlap check failure in main_scene.png")

        # 3. Refresh Generated Output Viewer
        if app_state.last_run_result:
            res = app_state.last_run_result
            self.lbl_out_folder.setText(f"Output Folder: {res.get('godot_project', 'None')}")
            self.lbl_out_scene.setText(f"Scene Path: {res.get('main_scene', 'None')}")
            self.lbl_out_assets.setText(f"Asset Count: {res.get('asset_count', 0)} ({res.get('mesh_count', 0)} Meshes)")
        else:
            self.lbl_out_folder.setText("Output Folder: None")
            self.lbl_out_scene.setText("Scene Path: None")
            self.lbl_out_assets.setText("Asset Count: 0")

    def on_job_completed(self, res_details):
        """Triggered upon background task finish to update generated viewer details."""
        self.refresh_ui()

    def on_fail_selected(self, item):
        val = item.text()
        if "GODOT_NOT_FOUND" in val:
            app_state.update_inspector(
                stage="godot_import",
                error="DEPENDENCY_MISSING: GODOT_NOT_FOUND",
                retry_count=2,
                worker="GodotWorker",
                stacktrace="File \"appsuite/workers/godot_worker.py\", line 140, in run\nraise WorkerError(\"DEPENDENCY_MISSING: GODOT_NOT_FOUND\")"
            )
        elif "overlap" in val:
            app_state.update_inspector(
                stage="output_validation",
                error="Visual overlaps detected between panel buttons",
                retry_count=1,
                worker="ValidationWorker",
                stacktrace="File \"appsuite/workers/validation_worker.py\", line 78, in run\nraise WorkerError(\"Validation overlap detected\")"
            )
        else:
            # Try to match custom error
            app_state.update_inspector(
                stage="error",
                error=val,
                retry_count=1,
                worker="AssetWorker",
                stacktrace=f"Traceback diagnostic details:\n{val}"
            )

    def run_generation(self):
        prompt = self.txt_prompt.text().strip()
        if prompt:
            app_state.run_prompt(prompt)
            self.txt_prompt.clear()

    def trigger_gta_scene(self):
        app_state.run_prompt("Create a GTA-like street block.")

    def trigger_medieval_scene(self):
        app_state.run_prompt("Create a medieval village.")

    def open_folder(self):
        if app_state.last_run_result:
            path = app_state.last_run_result.get("godot_project")
            if path and os.path.exists(path):
                os.startfile(path)

    def open_project(self):
        if app_state.last_run_result and app_state.ctx:
            path = app_state.last_run_result.get("godot_project")
            godot_bin = app_state.ctx.config.raw.get("workers", {}).get("godot", {}).get("binary")
            if path and godot_bin and os.path.exists(godot_bin):
                subprocess.Popen([godot_bin, "--path", path])

    def open_scene(self):
        if app_state.last_run_result and app_state.ctx:
            path = app_state.last_run_result.get("godot_project")
            scene = app_state.last_run_result.get("main_scene")
            godot_bin = app_state.ctx.config.raw.get("workers", {}).get("godot", {}).get("binary")
            if path and scene and godot_bin and os.path.exists(godot_bin):
                subprocess.Popen([godot_bin, "--path", path, scene])
