from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)
from desktop_ui.state.app_state import app_state
from desktop_ui.state.event_bus import event_bus


class TimelinePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelinePage")
        self.setStyleSheet("""
            QWidget#TimelinePage {
                background-color: #1a1a1a;
            }
            QLabel#PageTitle {
                color: #00ff66;
                font-family: 'Segoe UI';
                font-size: 20px;
                font-weight: bold;
            }
            QTableWidget {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
                color: #e0e0e0;
                gridline-color: #2d2d2d;
                font-family: 'Segoe UI', 'Consolas';
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget::item:selected {
                background-color: #3b3b3b;
                color: #00ff66;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #8c8c8c;
                border: none;
                border-bottom: 1px solid #2d2d2d;
                padding: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QLabel#HintLbl {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("System Execution Timeline", self)
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Table Widget (Phase 4: Timestamp, Stage, Worker, Duration, Message)
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Stage", "Worker", "Duration", "Message"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.itemClicked.connect(self.on_row_clicked)
        layout.addWidget(self.table, 1)

        # Hint
        hint = QLabel("Hint: Click any log line to inspect metrics, stacktraces, and validation statuses.", self)
        hint.setObjectName("HintLbl")
        layout.addWidget(hint)

        self.refresh_timeline()

        # Connect subscriptions
        event_bus.subscribe("TIMELINE_UPDATED", self.on_timeline_update)
        app_state.state_updated.connect(self.refresh_timeline)

    def refresh_timeline(self):
        # Prevent recursion if triggered from state change inside paint events
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        for idx, event in enumerate(app_state.timeline):
            self.table.insertRow(idx)
            
            # Form items
            item_time = QTableWidgetItem(event.get("timestamp", ""))
            item_stage = QTableWidgetItem(event.get("stage", "system"))
            item_worker = QTableWidgetItem(event.get("worker", "orchestrator"))
            
            # Map duration if available or default
            duration = event.get("duration")
            duration_str = f"{duration:.2f}s" if isinstance(duration, (int, float)) else "0.00s"
            item_dur = QTableWidgetItem(duration_str)
            
            item_msg = QTableWidgetItem(event.get("event", ""))
            
            # Set items
            self.table.setItem(idx, 0, item_time)
            self.table.setItem(idx, 1, item_stage)
            self.table.setItem(idx, 2, item_worker)
            self.table.setItem(idx, 3, item_dur)
            self.table.setItem(idx, 4, item_msg)
            
            # Level-based coloring
            level = event.get("level", "INFO").upper()
            color = QColor("#ffffff")
            if level == "ERROR":
                color = QColor("#ff3333")
            elif level == "WARNING":
                color = QColor("#ffcc00")
            elif level == "SUCCESS":
                color = QColor("#00ff66")
                
            for col in range(5):
                item = self.table.item(idx, col)
                if item:
                    item.setForeground(color)
                    
        self.table.blockSignals(False)

    def on_timeline_update(self, data):
        self.refresh_timeline()

    def on_row_clicked(self, item):
        row = self.table.row(item)
        if 0 <= row < len(app_state.timeline):
            event = app_state.timeline[row]
            app_state.update_inspector(
                stage=event.get("stage", "None"),
                error=event.get("error", "None"),
                retry_count=event.get("retry_count", 0),
                worker=event.get("worker", "None"),
                stacktrace=event.get("stacktrace") or f"Event details:\n{event.get('event')}"
            )
