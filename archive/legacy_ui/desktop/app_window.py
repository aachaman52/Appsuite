"""AppSuite Desktop — main application window.

Architecture:
  ┌─ Left Panel ──────────────────────────┐
  │  Prompt Input + Run button            │
  │  Job Queue                            │
  │  Resource Monitor                     │
  └───────────────────────────────────────┘
  ┌─ Center Panel ────────────────────────┐
  │  Pipeline Stage View                  │
  │  Live Log Viewer                      │
  └───────────────────────────────────────┘
  ┌─ Right Panel ─────────────────────────┐
  │  Asset Browser                        │
  │  Output Viewer                        │
  └───────────────────────────────────────┘
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

from .pipeline_thread import PipelineSignals, PipelineThread, ResourceThread
from .widgets.asset_browser import AssetBrowserWidget
from .widgets.job_queue_widget import JobQueueWidget
from .widgets.log_widget import LogWidget
from .widgets.output_viewer import OutputViewerWidget
from .widgets.pipeline_widget import PipelineWidget
from .widgets.resource_widget import ResourceWidget


class PromptPanel(QFrame):
    """Top-left prompt input area."""

    submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QLabel("PROMPT")
        header.setObjectName("section-title")
        layout.addWidget(header)

        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "Describe a game scene…\n\nExamples:\n"
            "  • A medieval village with houses and trees\n"
            "  • A sci-fi space station with corridors and props\n"
            "  • A fantasy dungeon with barrels and NPCs"
        )
        self._input.setFixedHeight(110)
        self._input.setAcceptRichText(False)
        layout.addWidget(self._input)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self._run_btn = QPushButton("▶  Run Pipeline")
        self._run_btn.setObjectName("primary-btn")
        self._run_btn.setMinimumHeight(38)
        self._run_btn.clicked.connect(self._on_run)
        btn_layout.addWidget(self._run_btn, 1)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(38)
        self._clear_btn.clicked.connect(self._input.clear)
        btn_layout.addWidget(self._clear_btn)

        layout.addWidget(btn_row)

        # Keyboard shortcut: Ctrl+Enter to run
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._on_run)

    def _on_run(self):
        text = self._input.toPlainText().strip()
        if text:
            self.submitted.emit(text)

    def set_running(self, running: bool):
        self._run_btn.setEnabled(not running)
        self._run_btn.setText("▶  Running…" if running else "▶  Run Pipeline")


class AppWindow(QMainWindow):
    """AppSuite Desktop main window."""

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.ctx = app_context
        self._signals = PipelineSignals()
        self._active_threads: Dict[str, PipelineThread] = {}
        self._active_job_id: Optional[str] = None

        self.setWindowTitle(f"AppSuite Desktop v{self.ctx.version}")
        self.setMinimumSize(1200, 720)
        self.resize(1400, 860)

        self._build_ui()
        self._connect_signals()
        self._start_resource_monitor()
        self._load_existing_jobs()

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    # ─── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Top bar ──
        top_bar = self._make_top_bar()
        root_layout.addWidget(top_bar)

        # ── Three-panel splitter ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        root_layout.addWidget(splitter, 1)

        # Left panel
        left = QWidget()
        left.setMinimumWidth(260)
        left.setMaximumWidth(380)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(6)

        self._prompt_panel = PromptPanel()
        self._prompt_panel.submitted.connect(self._on_prompt_submitted)
        left_layout.addWidget(self._prompt_panel)

        self._job_queue = JobQueueWidget()
        left_layout.addWidget(self._job_queue, 1)

        self._resource_widget = ResourceWidget()
        self._resource_widget.setFixedHeight(220)
        left_layout.addWidget(self._resource_widget)

        splitter.addWidget(left)

        # Center panel
        center = QWidget()
        center.setMinimumWidth(380)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(4, 8, 4, 8)
        center_layout.setSpacing(6)

        self._pipeline_widget = PipelineWidget()
        self._pipeline_widget.setFixedHeight(260)
        center_layout.addWidget(self._pipeline_widget)

        self._log_widget = LogWidget()
        center_layout.addWidget(self._log_widget, 1)

        splitter.addWidget(center)

        # Right panel
        right = QWidget()
        right.setMinimumWidth(280)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)
        right_layout.setSpacing(6)

        self._asset_browser = AssetBrowserWidget(db=self.ctx.db)
        right_layout.addWidget(self._asset_browser, 1)

        self._output_viewer = OutputViewerWidget()
        self._output_viewer.setFixedHeight(240)
        right_layout.addWidget(self._output_viewer)

        splitter.addWidget(right)
        splitter.setSizes([300, 550, 350])

        # Godot launch notification banner (hidden until Godot launches)
        self._godot_banner = QFrame()
        self._godot_banner.setFixedHeight(38)
        self._godot_banner.setStyleSheet(
            "background: #14532d; border-top: 1px solid #22c55e;"
        )
        banner_layout = QHBoxLayout(self._godot_banner)
        banner_layout.setContentsMargins(16, 0, 16, 0)
        self._godot_banner_label = QLabel("")
        self._godot_banner_label.setStyleSheet(
            "color: #22c55e; font-size: 12px; font-weight: 700;"
        )
        banner_layout.addWidget(self._godot_banner_label)
        banner_layout.addStretch()
        self._godot_banner_close = QPushButton("✕")
        self._godot_banner_close.setFixedSize(24, 24)
        self._godot_banner_close.setStyleSheet(
            "background: transparent; border: none; color: #22c55e;"
        )
        self._godot_banner_close.clicked.connect(lambda: self._godot_banner.hide())
        banner_layout.addWidget(self._godot_banner_close)
        self._godot_banner.hide()
        root_layout.addWidget(self._godot_banner)

    def _make_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            "background: #12151f; border-bottom: 2px solid #4f8ef7;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel("AppSuite Desktop")
        title.setObjectName("app-title")
        layout.addWidget(title)

        version = QLabel(f"v{self.ctx.version}")
        version.setObjectName("version-label")
        layout.addWidget(version)

        layout.addStretch()

        # Quick stats
        self._stat_queued = self._make_stat_chip("Queued", "0", "#6b7280")
        self._stat_running = self._make_stat_chip("Running", "0", "#f59e0b")
        self._stat_done = self._make_stat_chip("Done", "0", "#22c55e")
        self._stat_failed = self._make_stat_chip("Failed", "0", "#ef4444")

        for w in [self._stat_queued, self._stat_running, self._stat_done, self._stat_failed]:
            layout.addWidget(w)

        return bar

    def _make_stat_chip(self, label: str, value: str, colour: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: #1a1d27; border: 1px solid {colour}40; border-radius: 6px; padding: 2px 8px;")
        h = QHBoxLayout(w)
        h.setContentsMargins(6, 2, 6, 2)
        h.setSpacing(4)
        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"color: {colour}; font-weight: 700; font-size: 14px;")
        val_lbl.setFixedWidth(24)
        val_lbl.setAlignment(Qt.AlignCenter)
        name_lbl = QLabel(label)
        name_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
        h.addWidget(val_lbl)
        h.addWidget(name_lbl)
        w._val_lbl = val_lbl  # store reference
        return w

    # ─── Signal connections ────────────────────────────────────────────────────

    def _connect_signals(self):
        sig = self._signals
        sig.started.connect(self._on_job_started)
        sig.finished.connect(self._on_job_finished)
        sig.failed.connect(self._on_job_failed)
        sig.stage_started.connect(self._on_stage_started)
        sig.stage_done.connect(self._on_stage_done)
        sig.progress.connect(self._on_progress)
        sig.log_line.connect(self._on_log_line)
        sig.asset_found.connect(self._on_asset_found)
        self._job_queue.job_selected.connect(self._on_job_selected)

    # ─── Resource monitor ──────────────────────────────────────────────────────

    def _start_resource_monitor(self):
        self._res_thread = ResourceThread(interval_ms=2500, parent=self)
        self._res_thread.update.connect(self._resource_widget.update_resources)
        self._res_thread.start()

    # ─── Existing jobs ────────────────────────────────────────────────────────

    def _load_existing_jobs(self):
        try:
            jobs = self.ctx.db.list_jobs(50)
            self._job_queue.load_jobs(jobs)
            self._update_stats()
        except Exception:
            pass

    def _update_stats(self):
        try:
            rows = self.ctx.db.list_jobs(500)
        except Exception:
            return
        counts: Dict[str, int] = {}
        for r in rows:
            s = r["status"]
            counts[s] = counts.get(s, 0) + 1
        self._stat_queued._val_lbl.setText(str(counts.get("queued", 0)))
        self._stat_running._val_lbl.setText(str(counts.get("running", 0)))
        self._stat_done._val_lbl.setText(str(counts.get("completed", 0)))
        self._stat_failed._val_lbl.setText(str(counts.get("failed", 0)))

    # ─── Prompt submission ────────────────────────────────────────────────────

    @Slot(str)
    def _on_prompt_submitted(self, prompt: str):
        job_id = str(uuid.uuid4())
        try:
            self.ctx.db.create_job(job_id, prompt, None)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", str(e))
            return

        job = self.ctx.db.get_job(job_id)
        self._job_queue.add_job(job_id, prompt)
        self._pipeline_widget.reset()
        self._log_widget.append_separator(f"Job {job_id[:8]}")
        self._log_widget.append_line("info", f"[queue] Submitted job {job_id[:8]}: {prompt[:60]}")
        self._prompt_panel.set_running(True)
        self._active_job_id = job_id

        thread = PipelineThread(job_id, job, self.ctx.pipeline, self._signals, parent=self)
        thread.finished.connect(lambda: self._on_thread_finished(job_id))
        self._active_threads[job_id] = thread
        thread.start()

        self.status_bar.showMessage(f"Running job {job_id[:8]}…")
        self._update_stats()

    def _on_thread_finished(self, job_id: str):
        self._active_threads.pop(job_id, None)

    # ─── Pipeline signal handlers ─────────────────────────────────────────────

    @Slot(str)
    def _on_job_started(self, job_id: str):
        self._job_queue.update_job(job_id, "running", "dispatch", 0.0)
        self._update_stats()

    @Slot(str, dict)
    def _on_job_finished(self, job_id: str, summary: dict):
        self._job_queue.update_job(job_id, "completed", "done", 1.0)
        self._prompt_panel.set_running(False)
        self._update_stats()
        # Update output viewer
        job = self.ctx.db.get_job(job_id)
        if job and job.get("result_json"):
            job["result"] = json.loads(job["result_json"])
            self._output_viewer.show_job(job)
        self._asset_browser._refresh()

        # Show completion summary in status bar
        godot = summary.get("godot_import", {})
        editor_launched = godot.get("editor_launched", False) if isinstance(godot, dict) else False
        if editor_launched:
            project = godot.get("project", "") if isinstance(godot, dict) else ""
            self.status_bar.showMessage(
                f"✓ Job {job_id[:8]} done · Godot Editor open · {Path(project).name}"
            )
        else:
            self.status_bar.showMessage(f"✓ Job {job_id[:8]} completed")

    @Slot(str, str)
    def _on_job_failed(self, job_id: str, error: str):
        self._job_queue.update_job(job_id, "failed", "error", 1.0)
        self._prompt_panel.set_running(False)
        self.status_bar.showMessage(f"Job {job_id[:8]} FAILED: {error[:60]}")
        self._log_widget.append_line("error", f"[error] {error}")
        self._update_stats()

    @Slot(str, str)
    def _on_stage_started(self, job_id: str, stage: str):
        if job_id == self._active_job_id:
            self._pipeline_widget.on_stage_started(stage)
        self.status_bar.showMessage(f"Stage: {stage}")

    @Slot(str, str, float, dict)
    def _on_stage_done(self, job_id: str, stage: str, duration_s: float, result: dict):
        if job_id == self._active_job_id:
            self._pipeline_widget.on_stage_done(stage, duration_s, result)

        # When Godot import stage completes, show editor-launch notification
        if stage == "godot_import" and job_id == self._active_job_id:
            launched = result.get("editor_launched", False)
            assets_imported = result.get("assets_imported", 0)
            import_files = result.get("import_files", 0)
            project = result.get("project", "")

            detail_parts = []
            if import_files:
                detail_parts.append(f"{import_files} .import files")
            if assets_imported:
                detail_parts.append(f"{assets_imported} compiled resources")
            detail = ", ".join(detail_parts)

            if launched:
                self._godot_banner_label.setText(
                    f"✓  Godot Editor opened · {detail} · {project}"
                )
                self._godot_banner.show()
                self._log_widget.append_line(
                    "info",
                    f"[godot_launch] Godot Editor launched with project: {project}",
                )
            else:
                msg = result.get("editor_msg", "")
                self._log_widget.append_line(
                    "warn",
                    f"[godot_launch] Godot Editor did not launch: {msg}",
                )
            # Mark godot_launch stage accordingly
            if launched:
                self._pipeline_widget.on_stage_done("godot_launch", 0.0, {"launched": True})
            else:
                self._pipeline_widget.on_stage_failed("godot_launch", result.get("editor_msg", "not launched"))

    @Slot(str, float)
    def _on_progress(self, job_id: str, pct: float):
        self._job_queue.update_job(job_id, "running", "", pct)

    @Slot(str, str, str)
    def _on_log_line(self, job_id: str, level: str, message: str):
        self._log_widget.append_line(level, message)

    @Slot(str, dict)
    def _on_asset_found(self, job_id: str, asset: dict):
        self._asset_browser.add_asset(asset)

    @Slot(str)
    def _on_job_selected(self, job_id: str):
        try:
            job = self.ctx.db.get_job(job_id)
            if job:
                if job.get("result_json"):
                    job["result"] = json.loads(job["result_json"])
                self._output_viewer.show_job(job)
        except Exception:
            pass

    # ─── Cleanup ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        # Stop resource monitor
        if hasattr(self, "_res_thread"):
            self._res_thread.stop()
            self._res_thread.wait(2000)
        # Stop any running pipeline threads
        for thread in self._active_threads.values():
            thread.quit()
            thread.wait(3000)
        # Shutdown backend
        try:
            self.ctx.shutdown()
        except Exception:
            pass
        event.accept()
