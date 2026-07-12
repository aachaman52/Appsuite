from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from desktop_ui.state.event_bus import event_bus


class Sidebar(QWidget):
    page_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(64)
        
        # Style sheet override for sidebar background
        self.setStyleSheet("""
            QWidget#Sidebar {
                background-color: #212121;
                border-right: 1px solid #2d2d2d;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: 14px;
                padding: 12px;
                min-height: 48px;
                max-height: 48px;
            }
            QPushButton:hover {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QPushButton[active="true"] {
                background-color: #1a1a1a;
                color: #00ff66;
                border-left: 3px solid #00ff66;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        
        nav_items = [
            ("D", "dashboard", "Dashboard"),
            ("W", "workers", "Workers"),
            ("T", "timeline", "Timeline"),
            ("A", "assets", "Assets"),
            ("S", "settings", "Settings")
        ]

        self.buttons = {}
        for icon, page_id, tooltip in nav_items:
            btn = QPushButton(icon, self)
            btn.setToolTip(tooltip)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setProperty("active", "false")
            
            # Click connection
            btn.clicked.connect(lambda checked=False, pid=page_id: self.select_page(pid))
            
            layout.addWidget(btn)
            self.buttons[page_id] = btn

        # Spacer at the bottom to push buttons to top
        layout.addStretch()
        
        # Select dashboard visually by default
        self.select_page("dashboard", publish=False)

    def select_page(self, page_id: str, publish=True):
        # Deselect all buttons
        for pid, btn in self.buttons.items():
            btn.setProperty("active", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
            
        # Select target button
        if page_id in self.buttons:
            btn = self.buttons[page_id]
            btn.setProperty("active", "true")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
            
        self.page_selected.emit(page_id)
        if publish:
            event_bus.publish("SIDEBAR_NAVIGATED", {"page": page_id})
