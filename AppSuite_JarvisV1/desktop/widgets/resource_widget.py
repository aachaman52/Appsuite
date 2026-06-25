"""Widget: Resource monitor — CPU, RAM, Disk gauges + worker status."""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)


class GaugeWidget(QWidget):
    """SVG-style circular gauge drawn in QPainter."""

    def __init__(self, label: str, unit: str = "%", parent=None):
        super().__init__(parent)
        self.label = label
        self.unit = unit
        self._value: Optional[float] = None
        self.setFixedSize(90, 100)

    def set_value(self, v: Optional[float]):
        self._value = v
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 45, 45, 32

        # Background ring
        p.setPen(QPen(QColor("#2a2d3e"), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        if self._value is not None:
            pct = max(0, min(100, self._value))
            if pct >= 85:
                colour = QColor("#ef4444")
            elif pct >= 60:
                colour = QColor("#f59e0b")
            else:
                colour = QColor("#22c55e")

            # Arc (360 * pct/100 degrees, starting from -90°)
            p.setPen(QPen(colour, 8, Qt.SolidLine, Qt.RoundCap))
            span = int(-360 * 16 * pct / 100)
            p.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, span)

            # Value text
            p.setPen(QColor("#e8eaf0"))
            f = QFont("Segoe UI", 10, QFont.Bold)
            p.setFont(f)
            p.drawText(cx - 25, cy - 8, 50, 22,
                       Qt.AlignCenter, f"{pct:.0f}{self.unit}")
        else:
            p.setPen(QColor("#6b7280"))
            f = QFont("Segoe UI", 9)
            p.setFont(f)
            p.drawText(cx - 20, cy - 8, 40, 22, Qt.AlignCenter, "—")

        # Label below
        p.setPen(QColor("#6b7280"))
        f = QFont("Segoe UI", 8)
        p.setFont(f)
        p.drawText(0, cy + r + 6, 90, 18, Qt.AlignCenter, self.label)

        p.end()


class ResourceWidget(QFrame):
    """Real-time resource monitor: CPU / RAM / Disk + active workers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        title = QLabel("RESOURCES")
        title.setObjectName("section-title")
        layout.addWidget(title)

        # Gauges row
        gauge_row = QWidget()
        gauge_layout = QHBoxLayout(gauge_row)
        gauge_layout.setContentsMargins(0, 0, 0, 0)
        gauge_layout.setSpacing(8)

        self._cpu_gauge = GaugeWidget("CPU")
        self._ram_gauge = GaugeWidget("RAM")
        self._disk_gauge = GaugeWidget("Disk")

        gauge_layout.addWidget(self._cpu_gauge)
        gauge_layout.addWidget(self._ram_gauge)
        gauge_layout.addWidget(self._disk_gauge)
        gauge_layout.addStretch()
        layout.addWidget(gauge_row)

        # Text details
        self._details = QLabel("Waiting for data…")
        self._details.setStyleSheet("color: #6b7280; font-size: 11px;")
        self._details.setWordWrap(True)
        layout.addWidget(self._details)

        # Worker status
        worker_title = QLabel("ACTIVE WORKERS")
        worker_title.setObjectName("section-title")
        layout.addWidget(worker_title)

        self._worker_label = QLabel("—")
        self._worker_label.setStyleSheet("color: #e8eaf0; font-size: 12px;")
        layout.addWidget(self._worker_label)

        layout.addStretch()

    def update_resources(self, data: Dict[str, Any]):
        cpu = data.get("cpu_pct")
        ram = data.get("ram_pct")
        disk = data.get("disk_pct")

        self._cpu_gauge.set_value(cpu)
        self._ram_gauge.set_value(ram)
        self._disk_gauge.set_value(disk)

        details_parts = []
        if data.get("ram_used_mb") is not None:
            details_parts.append(
                f"RAM: {data['ram_used_mb']} / {data['ram_total_mb']} MB"
            )
        if data.get("disk_free_gb") is not None:
            details_parts.append(
                f"Disk: {data['disk_free_gb']:.1f} GB free"
            )
        self._details.setText("  ·  ".join(details_parts) or "psutil not available")

    def set_active_workers(self, workers: list):
        if workers:
            self._worker_label.setText("  |  ".join(workers))
            self._worker_label.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: 700;")
        else:
            self._worker_label.setText("Idle")
            self._worker_label.setStyleSheet("color: #22c55e; font-size: 12px;")
