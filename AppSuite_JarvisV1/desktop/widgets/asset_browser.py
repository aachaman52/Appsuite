"""Widget: Asset browser — shows all downloaded assets with search."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

SOURCE_COLOURS = {
    "kenney":        "#7c3aed",
    "poly_pizza":    "#0891b2",
    "polyhaven":     "#15803d",
    "openai":        "#d97706",
    "local_library": "#6b7280",
}


class AssetBrowserWidget(QFrame):
    """Live-updating asset table with search and file-open capability."""

    COLUMNS = ["Name", "Role", "Source", "Format", "Quality", "Size"]

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._db = db
        self._assets: List[Dict[str, Any]] = []
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # refresh every 5 s

    def set_db(self, db):
        self._db = db
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(8)

        title = QLabel("ASSET BROWSER")
        title.setObjectName("section-title")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)
        h_layout.addWidget(self._search)

        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(32, 28)
        self._refresh_btn.clicked.connect(self._refresh)
        h_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # Count label
        self._count_label = QLabel("0 assets")
        self._count_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 0 12px 6px 12px;")
        layout.addWidget(self._count_label)

        # Table
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.doubleClicked.connect(self._open_file_location)
        layout.addWidget(self._table, 1)

        # Footer
        footer = QWidget()
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 6, 12, 6)
        tip = QLabel("Double-click a row to open its file location")
        tip.setStyleSheet("color: #6b7280; font-size: 11px;")
        f_layout.addWidget(tip)
        layout.addWidget(footer)

    def add_asset(self, asset: Dict[str, Any]):
        """Called when a new asset is discovered during a job."""
        if any(a.get("id") == asset.get("id") for a in self._assets):
            return
        self._assets.append(asset)
        self._apply_filter(self._search.text())

    def _refresh(self):
        if not self._db:
            return
        try:
            rows = self._db.list_assets(limit=300)
            self._assets = rows
            self._apply_filter(self._search.text())
        except Exception:
            pass

    def _apply_filter(self, text: str):
        q = text.lower().strip()
        shown = [
            a for a in self._assets
            if not q or q in (a.get("name") or "").lower()
               or q in (a.get("source") or "").lower()
               or q in (a.get("role") or "").lower()
        ]
        self._count_label.setText(f"{len(shown)} assets")
        self._table.setRowCount(0)
        for asset in shown:
            self._add_row(asset)

    def _add_row(self, asset: Dict[str, Any]):
        row = self._table.rowCount()
        self._table.insertRow(row)

        name = QTableWidgetItem(asset.get("name") or "—")
        name.setToolTip(asset.get("file_path") or "")
        self._table.setItem(row, 0, name)

        self._table.setItem(row, 1, QTableWidgetItem(asset.get("role") or "—"))

        source = asset.get("source") or "—"
        src_item = QTableWidgetItem(source)
        colour = SOURCE_COLOURS.get(source, "#6b7280")
        src_item.setForeground(Qt.GlobalColor.white)
        src_item.setBackground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(colour))
        self._table.setItem(row, 2, src_item)

        fmt = (asset.get("format") or "—").upper()
        self._table.setItem(row, 3, QTableWidgetItem(fmt))

        score = asset.get("quality_score")
        score_text = f"{score * 100:.0f}%" if score is not None else "—"
        self._table.setItem(row, 4, QTableWidgetItem(score_text))

        fp = asset.get("file_path")
        if fp:
            size = Path(fp).stat().st_size if Path(fp).exists() else 0
            size_text = f"{size // 1024} KB" if size >= 1024 else f"{size} B"
        else:
            size_text = "—"
        self._table.setItem(row, 5, QTableWidgetItem(size_text))

    def _open_file_location(self):
        row = self._table.currentRow()
        if row < 0:
            return
        name_item = self._table.item(row, 0)
        if not name_item:
            return
        fp = name_item.toolTip()
        if fp and Path(fp).exists():
            parent = str(Path(fp).parent)
            subprocess.Popen(["explorer", parent], shell=True)
