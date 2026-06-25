"""Widget: Live log viewer — displays colour-coded pipeline log lines."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

LEVEL_COLOURS = {
    "error": "#ef4444",
    "warn":  "#f59e0b",
    "warning": "#f59e0b",
    "info":  "#e8eaf0",
    "debug": "#6b7280",
}

STAGE_COLOURS = {
    "asset_search":     "#4f8ef7",
    "blender_import":   "#a855f7",
    "godot_import":     "#22c55e",
    "asset_processing": "#06b6d4",
    "output_validation":"#f59e0b",
    "memory":           "#ec4899",
    "error":            "#ef4444",
    "queue":            "#6b7280",
    "recovery":         "#f59e0b",
    "done":             "#22c55e",
}


class LogWidget(QFrame):
    """Colour-coded, auto-scrolling log panel."""

    MAX_LINES = 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._line_count = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("PIPELINE LOGS")
        title.setObjectName("section-title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedSize(60, 26)
        self._clear_btn.clicked.connect(self.clear)
        header_layout.addWidget(self._clear_btn)

        layout.addWidget(header)

        # Log text area
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.NoWrap)
        mono = QFont("Consolas", 11)
        mono.setStyleHint(QFont.Monospace)
        self._text.setFont(mono)
        self._text.setStyleSheet(
            "background-color: #0a0c12; border: none; border-top: 1px solid #2a2d3e;"
        )
        layout.addWidget(self._text, 1)

    def append_line(self, level: str, message: str):
        """Append a single log line with colour formatting."""
        if self._line_count >= self.MAX_LINES:
            # Trim first 20% of lines
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(
                QTextCursor.Down, QTextCursor.KeepAnchor,
                self.MAX_LINES // 5,
            )
            cursor.removeSelectedText()
            self._line_count = self.MAX_LINES - self.MAX_LINES // 5

        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        colour = LEVEL_COLOURS.get(level.lower(), "#e8eaf0")
        fmt.setForeground(QColor(colour))
        cursor.setCharFormat(fmt)
        cursor.insertText(message + "\n")

        self._line_count += 1
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def append_blender_log(self, text: str):
        """Append Blender subprocess output with a purple prefix."""
        for line in text.splitlines():
            if not line.strip():
                continue
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.End)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#a855f7"))
            cursor.setCharFormat(fmt)
            cursor.insertText(f"[blender] {line}\n")
            self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def append_godot_log(self, text: str):
        """Append Godot subprocess output with a green prefix."""
        for line in text.splitlines():
            if not line.strip():
                continue
            cursor = self._text.textCursor()
            cursor.movePosition(QTextCursor.End)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#22c55e"))
            cursor.setCharFormat(fmt)
            cursor.insertText(f"[godot] {line}\n")
            self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def append_separator(self, label: str = ""):
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#2a2d3e"))
        cursor.setCharFormat(fmt)
        sep = "─" * 60
        cursor.insertText(f"\n{sep} {label} {sep}\n\n")
        self._text.setTextCursor(cursor)

    def clear(self):
        self._text.clear()
        self._line_count = 0
