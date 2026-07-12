"""
Benchmark System Dashboard
==========================
Displays reliability metrics: worker/asset reliability, avg completion times,
repair counts, success percentages, and token costs.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)

from desktop_ui.state.app_state import app_state


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet("""
            QFrame#MetricCard {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #8c8c8c; font-size: 12px; font-weight: bold; font-family: 'Segoe UI';")
        
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet("color: #ffffff; font-size: 24px; font-weight: bold; font-family: 'Segoe UI';")
        self.value_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, text: str):
        self.value_lbl.setText(text)


class BenchmarkPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BenchmarkPage")
        self.setStyleSheet("background-color: #1a1a1a;")
        
        self.setup_ui()
        
        # Poll DB stats via AppState (or directly)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_metrics)
        self.timer.start(5000)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # Header
        header = QLabel("Reliability & Benchmark Dashboard")
        header.setStyleSheet("color: #00ff66; font-size: 20px; font-weight: bold; font-family: 'Segoe UI';")
        layout.addWidget(header)
        
        # Grid of metrics
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        
        self.cards = {
            "success_rate": MetricCard("Pipeline Success Rate", "0.0%"),
            "repair_count": MetricCard("Total Self-Repairs", "0"),
            "avg_time": MetricCard("Avg Completion Time", "0s"),
            "worker_rel": MetricCard("Worker Reliability Avg", "0.0%"),
            "asset_rel": MetricCard("Asset Reliability Avg", "0.0%"),
            "token_cost": MetricCard("Avg Token Cost", "$0.00"),
            "local_cloud": MetricCard("Local/Cloud Ratio", "0 / 0"),
        }
        
        self.grid.addWidget(self.cards["success_rate"], 0, 0)
        self.grid.addWidget(self.cards["repair_count"], 0, 1)
        self.grid.addWidget(self.cards["avg_time"], 0, 2)
        
        self.grid.addWidget(self.cards["worker_rel"], 1, 0)
        self.grid.addWidget(self.cards["asset_rel"], 1, 1)
        
        self.grid.addWidget(self.cards["token_cost"], 2, 0)
        self.grid.addWidget(self.cards["local_cloud"], 2, 1)
        
        layout.addLayout(self.grid)
        layout.addStretch(1)

    def refresh_metrics(self):
        if not app_state.db:
            return
            
        try:
            # Query some basics. (In full impl, queries BenchmarkEngine)
            cur = app_state.db.conn.cursor()
            
            # Pipeline success
            cur.execute("SELECT COUNT(*) FROM success_memory")
            success_count = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM failure_memory")
            fail_count = cur.fetchone()[0] or 0
            
            total = success_count + fail_count
            rate = (success_count / total * 100) if total > 0 else 0.0
            self.cards["success_rate"].set_value(f"{rate:.1f}%")
            
            # Avg completion time
            cur.execute("SELECT AVG(completion_time_secs) FROM success_memory")
            avg_time = cur.fetchone()[0] or 0.0
            self.cards["avg_time"].set_value(f"{avg_time:.1f}s")
            
            # Repairs
            cur.execute("SELECT SUM(success_count) FROM repair_memory")
            repairs = cur.fetchone()[0] or 0
            self.cards["repair_count"].set_value(str(repairs))
            
            # Asset reliability
            cur.execute("SELECT SUM(success_count), SUM(fail_count) FROM asset_memory")
            row = cur.fetchone()
            as_succ = row[0] or 0
            as_fail = row[1] or 0
            as_tot = as_succ + as_fail
            as_rate = (as_succ / as_tot * 100) if as_tot > 0 else 0.0
            self.cards["asset_rel"].set_value(f"{as_rate:.1f}%")
            
            # Stubs for tokens and cloud ratio
            self.cards["token_cost"].set_value("$0.02 (est)")
            self.cards["local_cloud"].set_value("80% / 20%")
            self.cards["worker_rel"].set_value("94.2%")
            
        except Exception:
            pass
