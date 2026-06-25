"""Widget: Job queue — shows submitted jobs with live status updates."""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QVBoxLayout, QWidget,
)

STATUS_ICONS = {
    "queued":    "⏳",
    "running":   "▶",
    "completed": "✓",
    "failed":    "✗",
}

STATUS_COLOURS = {
    "queued":    "#6b7280",
    "running":   "#f59e0b",
    "completed": "#22c55e",
    "failed":    "#ef4444",
}


class JobItem(QWidget):
    """Single row in the job queue list."""

    def __init__(self, job_id: str, prompt: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Top row: icon + truncated prompt
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self._icon = QLabel("⏳")
        self._icon.setFixedWidth(18)
        top_layout.addWidget(self._icon)

        self._prompt_label = QLabel(prompt[:60] + ("…" if len(prompt) > 60 else ""))
        self._prompt_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        top_layout.addWidget(self._prompt_label, 1)

        self._status_label = QLabel("queued")
        self._status_label.setStyleSheet(f"color: {STATUS_COLOURS['queued']}; font-size: 11px;")
        self._status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top_layout.addWidget(self._status_label)

        layout.addWidget(top)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(4)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

        # Stage label
        self._stage_label = QLabel("")
        self._stage_label.setStyleSheet("color: #6b7280; font-size: 10px;")
        layout.addWidget(self._stage_label)

    def update_status(self, status: str, stage: str = "", progress: float = 0.0):
        icon = STATUS_ICONS.get(status, "•")
        colour = STATUS_COLOURS.get(status, "#6b7280")
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")
        self._bar.setValue(int(progress * 100))
        if stage:
            self._stage_label.setText(f"Stage: {stage}")
        if status == "completed":
            self._bar.setObjectName("progress-green")
            self._bar.setStyleSheet("")
        elif status == "failed":
            self._bar.setObjectName("progress-red")
            self._bar.setStyleSheet("")
        elif status == "running":
            self._bar.setObjectName("progress-amber")
            self._bar.setStyleSheet("")


class JobQueueWidget(QFrame):
    """Scrollable list of all submitted jobs with live status."""

    job_selected = Signal(str)  # emits job_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._job_items: Dict[str, tuple] = {}  # job_id -> (QListWidgetItem, JobItem)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("JOB QUEUE")
        title.setObjectName("section-title")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._count_label = QLabel("0 jobs")
        self._count_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        h_layout.addWidget(self._count_label)

        layout.addWidget(header)

        # List
        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

    def add_job(self, job_id: str, prompt: str):
        item = QListWidgetItem()
        widget = JobItem(job_id, prompt)
        item.setSizeHint(widget.sizeHint())
        self._list.insertItem(0, item)
        self._list.setItemWidget(item, widget)
        self._job_items[job_id] = (item, widget)
        self._list.setCurrentItem(item)
        self._update_count()

    def update_job(self, job_id: str, status: str, stage: str = "", progress: float = 0.0):
        entry = self._job_items.get(job_id)
        if entry:
            _, widget = entry
            widget.update_status(status, stage, progress)

    def load_jobs(self, jobs: List[Dict[str, Any]]):
        """Populate from existing DB records on startup."""
        for job in reversed(jobs):  # oldest first so newest shows at top
            job_id = job["id"]
            if job_id not in self._job_items:
                item = QListWidgetItem()
                widget = JobItem(job_id, job["prompt"])
                widget.update_status(
                    job["status"], job.get("stage") or "",
                    job.get("progress") or 0.0,
                )
                item.setSizeHint(widget.sizeHint())
                self._list.insertItem(0, item)
                self._list.setItemWidget(item, widget)
                self._job_items[job_id] = (item, widget)
        self._update_count()

    def _update_count(self):
        n = self._list.count()
        self._count_label.setText(f"{n} job{'s' if n != 1 else ''}")

    def _on_selection_changed(self, current, _previous):
        if not current:
            return
        for job_id, (item, _) in self._job_items.items():
            if item is current:
                self.job_selected.emit(job_id)
                break
