"""Widget: Stage pipeline view — shows each pipeline stage with status, duration, and progress."""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

STAGES = [
    ("asset_search",      "Asset Search"),
    ("asset_processing",  "Asset Analysis"),
    ("blender_import",    "Blender Import"),
    ("godot_import",      "Godot Import & Verify"),
    ("godot_launch",      "Editor Launch"),
    ("output_validation", "Validation"),
]

STATUS_STYLE = {
    "pending":  ("●", "#6b7280"),
    "running":  ("▶", "#f59e0b"),
    "done":     ("✓", "#22c55e"),
    "failed":   ("✗", "#ef4444"),
    "skipped":  ("⟳", "#4f8ef7"),
}


class StageRow(QWidget):
    def __init__(self, stage_key: str, stage_label: str, parent=None):
        super().__init__(parent)
        self.stage_key = stage_key
        self._status = "pending"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Status icon
        self._icon = QLabel("●")
        self._icon.setFixedWidth(18)
        self._icon.setAlignment(Qt.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(11)
        self._icon.setFont(icon_font)

        # Stage name
        self._name = QLabel(stage_label)
        self._name.setFixedWidth(160)
        self._name.setStyleSheet("color: #6b7280;")

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(6)
        self._bar.setObjectName("progress-green")
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bar.setTextVisible(False)

        # Duration
        self._duration = QLabel("")
        self._duration.setFixedWidth(60)
        self._duration.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._duration.setStyleSheet("color: #6b7280; font-size: 11px;")

        # Detail
        self._detail = QLabel("")
        self._detail.setFixedWidth(160)
        self._detail.setStyleSheet("color: #6b7280; font-size: 11px;")
        self._detail.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self._icon)
        layout.addWidget(self._name)
        layout.addWidget(self._bar)
        layout.addWidget(self._duration)
        layout.addWidget(self._detail)

        self.setMaximumHeight(44)

    def set_running(self):
        self._status = "running"
        icon, colour = STATUS_STYLE["running"]
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._name.setStyleSheet(f"color: {colour}; font-weight: 700;")
        self._bar.setObjectName("progress-amber")
        self._bar.setValue(50)
        self._bar.setStyleSheet("")  # force repaint
        self.setStyleSheet("")

    def set_done(self, duration_s: float, detail: str = ""):
        self._status = "done"
        icon, colour = STATUS_STYLE["done"]
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._name.setStyleSheet(f"color: #e8eaf0; font-weight: 700;")
        self._bar.setObjectName("progress-green")
        self._bar.setValue(100)
        self._bar.setStyleSheet("")
        self._duration.setText(f"{duration_s:.1f}s")
        self._detail.setText(detail[:30])
        self._detail.setToolTip(detail)

    def set_failed(self, reason: str = ""):
        self._status = "failed"
        icon, colour = STATUS_STYLE["failed"]
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._name.setStyleSheet(f"color: {colour}; font-weight: 700;")
        self._bar.setObjectName("progress-red")
        self._bar.setValue(100)
        self._bar.setStyleSheet("")
        self._detail.setText(reason[:30])
        self._detail.setToolTip(reason)

    def set_skipped(self):
        self._status = "skipped"
        icon, colour = STATUS_STYLE["skipped"]
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._name.setStyleSheet(f"color: {colour};")
        self._bar.setValue(100)
        self._detail.setText("reused")

    def reset(self):
        self._status = "pending"
        icon, colour = STATUS_STYLE["pending"]
        self._icon.setText(icon)
        self._icon.setStyleSheet(f"color: {colour};")
        self._name.setStyleSheet("color: #6b7280;")
        self._bar.setValue(0)
        self._duration.setText("")
        self._detail.setText("")


class PipelineWidget(QFrame):
    """Visual stage-by-stage pipeline viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._rows: Dict[str, StageRow] = {}
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel("PIPELINE")
        title.setObjectName("section-title")
        title_layout.addWidget(title)
        title_layout.addStretch()
        outer.addWidget(title_row)

        # Column headers
        header = QWidget()
        header.setStyleSheet("background:#12151f; border-bottom: 1px solid #2a2d3e;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        h_layout.setSpacing(10)
        for text, width in [("", 18), ("Stage", 160), ("", -1), ("Time", 60), ("Detail", 160)]:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 700;")
            if width > 0:
                lbl.setFixedWidth(width)
            else:
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            h_layout.addWidget(lbl)
        outer.addWidget(header)

        # Stage rows
        for key, label in STAGES:
            row = StageRow(key, label)
            row.setStyleSheet("background: transparent; border-bottom: 1px solid #1a1d27;")
            self._rows[key] = row
            outer.addWidget(row)

        outer.addStretch()

    def reset(self):
        for row in self._rows.values():
            row.reset()

    def on_stage_started(self, stage: str):
        row = self._rows.get(stage)
        if row:
            row.set_running()

    def on_stage_done(self, stage: str, duration_s: float, result: dict):
        row = self._rows.get(stage)
        if row:
            # Build a human-readable detail from the result dict
            detail_parts = []
            for k, v in result.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    detail_parts.append(f"{k}={v}")
                elif isinstance(v, bool):
                    detail_parts.append(f"{k}={'✓' if v else '✗'}")
            detail = ", ".join(detail_parts[:3])
            row.set_done(duration_s, detail)

    def on_stage_failed(self, stage: str, reason: str):
        row = self._rows.get(stage)
        if row:
            row.set_failed(reason)

    def on_stage_skipped(self, stage: str):
        row = self._rows.get(stage)
        if row:
            row.set_skipped()
