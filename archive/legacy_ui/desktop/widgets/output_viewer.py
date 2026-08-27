"""Widget: Output viewer — shows completed job output files."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)


class OutputViewerWidget(QFrame):
    """Shows the manifest/result for a completed job."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._current_job_id: str | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("OUTPUT")
        title.setObjectName("section-title")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._open_btn = QPushButton("📂 Open Folder")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._open_folder)
        h_layout.addWidget(self._open_btn)
        layout.addWidget(header)

        # Summary labels
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(12, 6, 12, 6)
        info_layout.setSpacing(4)

        self._status_label = QLabel("No job selected")
        self._status_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        info_layout.addWidget(self._status_label)

        self._godot_label = QLabel("")
        self._godot_label.setStyleSheet("color: #22c55e; font-size: 11px;")
        self._godot_label.setWordWrap(True)
        info_layout.addWidget(self._godot_label)

        self._fbx_label = QLabel("")
        self._fbx_label.setStyleSheet("color: #4f8ef7; font-size: 11px;")
        self._fbx_label.setWordWrap(True)
        info_layout.addWidget(self._fbx_label)

        layout.addWidget(info_panel)

        # Manifest viewer
        self._manifest = QTextEdit()
        self._manifest.setReadOnly(True)
        self._manifest.setStyleSheet(
            "background: #0a0c12; border: none; border-top: 1px solid #2a2d3e; "
            "font-family: Consolas, monospace; font-size: 11px;"
        )
        layout.addWidget(self._manifest, 1)

    def show_job(self, job: Dict[str, Any]):
        self._current_job_id = job.get("id")
        status = job.get("status", "—")
        prompt = job.get("prompt", "")[:60]
        self._status_label.setText(f"{status.upper()} · {prompt}")

        result = job.get("result") or {}
        godot = result.get("godot_project") or result.get("main_scene") or ""
        fbx = result.get("fbx_path") or ""
        self._godot_label.setText(f"Godot: {godot}" if godot else "")
        self._fbx_label.setText(f"FBX: {fbx}" if fbx else "")

        # Load manifest if it exists
        import json
        manifest_path = None
        if godot:
            manifest_path = Path(godot).parent.parent / "manifest.json"
            if not manifest_path.exists():
                manifest_path = Path(godot).parent / "manifest.json"

        if manifest_path and manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._manifest.setPlainText(json.dumps(data, indent=2))
            except Exception as e:
                self._manifest.setPlainText(f"Error reading manifest: {e}")
        elif result:
            self._manifest.setPlainText(json.dumps(result, indent=2))
        else:
            self._manifest.setPlainText(f"Status: {status}\nJob ID: {self._current_job_id}\n")
            if job.get("error"):
                self._manifest.append(f"\nError:\n{job['error']}")

        self._open_btn.setEnabled(bool(godot or fbx))

    def clear(self):
        self._current_job_id = None
        self._status_label.setText("No job selected")
        self._godot_label.setText("")
        self._fbx_label.setText("")
        self._manifest.clear()
        self._open_btn.setEnabled(False)

    def _open_folder(self):
        import json
        result_text = self._manifest.toPlainText()
        try:
            data = json.loads(result_text)
        except Exception:
            return
        target = data.get("godot_project") or data.get("fbx_path")
        if target:
            folder = str(Path(target).parent)
            subprocess.Popen(["explorer", folder], shell=True)
