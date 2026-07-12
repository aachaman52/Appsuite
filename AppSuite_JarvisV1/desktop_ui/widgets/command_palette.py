from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QWidget
from desktop_ui.state.app_state import app_state
from desktop_ui.state.event_bus import event_bus


class CommandPalette(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Search Command Palette")
        self.setFixedSize(500, 300)
        
        # Borderless overlay dialog
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setStyleSheet("""
            QDialog {
                background-color: #212121;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QLineEdit {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 14px;
                padding: 8px 12px;
            }
            QLineEdit:focus {
                border-color: #00ff66;
            }
            QListWidget {
                background-color: #212121;
                border: none;
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #2d2d2d;
            }
            QListWidget::item:selected {
                background-color: #2d2d2d;
                color: #00ff66;
            }
        """)

        # Center relative to parent window
        if parent:
            px = parent.x() + (parent.width() - 500) // 2
            py = parent.y() + 100
            self.move(px, py)

        self.search_db = self.build_search_database()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Search Input
        self.entry = QLineEdit(self)
        self.entry.setPlaceholderText("Search or type a command...")
        self.entry.textChanged.connect(self.on_search)
        self.entry.returnPressed.connect(self.on_submit)
        layout.addWidget(self.entry)

        # List Widget
        self.listbox = QListWidget(self)
        self.listbox.itemDoubleClicked.connect(self.on_submit)
        layout.addWidget(self.listbox)

        # Populate initially
        self.show_initial_items()
        self.entry.setFocus()

    def build_search_database(self) -> list:
        db = []
        for w in app_state.workers.keys():
            db.append({"label": f"Worker: {w}", "type": "worker", "value": w})
        for j in app_state.jobs:
            db.append({"label": f"Job ID {j['id'][:8]}: {j['prompt']}", "type": "job", "value": j['id']})
            
        db.append({"label": "Template: Medieval Village", "type": "template", "value": "medieval_village"})
        db.append({"label": "Template: GTA Street Block", "type": "template", "value": "gta_scene"})
        db.append({"label": "Memory: semantic_vectors.db", "type": "memory", "value": "semantic_vectors"})
        db.append({"label": "Memory: strategy_matrix.json", "type": "memory", "value": "strategy_matrix"})
        db.append({"label": "Action: Restart godot_worker", "type": "action", "value": "restart_godot"})
        db.append({"label": "Action: Show System Health Logs", "type": "action", "value": "health_logs"})
        return db

    def show_initial_items(self):
        self.listbox.clear()
        for item in self.search_db:
            self.listbox.addItem(item["label"])

    def on_search(self, text):
        query = text.strip().lower()
        self.listbox.clear()
        
        if not query:
            self.show_initial_items()
            return
            
        for item in self.search_db:
            if query in item["label"].lower() or query in item["type"]:
                self.listbox.addItem(item["label"])

    def on_submit(self):
        current_item = self.listbox.currentItem()
        if current_item:
            label = current_item.text()
            match = next((item for item in self.search_db if item["label"] == label), None)
            if match:
                self.dispatch_action(match)
        self.close()

    def dispatch_action(self, item: dict):
        app_state.add_timeline_event(f"Command palette executed action: {item['label']}")
        if item["type"] == "worker":
            event_bus.publish("NAVIGATE_TO", {"page": "workers"})
        elif item["type"] == "job":
            event_bus.publish("NAVIGATE_TO", {"page": "timeline"})
        elif item["value"] == "restart_godot":
            app_state.workers["godot_worker"]["status"] = "Healthy"
            app_state.workers["godot_worker"]["task"] = "Idle"
            event_bus.publish("TIMELINE_UPDATED", {
                "timestamp": "now", 
                "event": "godot_worker restarted successfully", 
                "level": "INFO"
            })

    def event(self, event):
        # Close overlay if user clicks outside of dialog area
        if event.type() == QEvent.WindowDeactivate:
            self.close()
            return True
        return super().event(event)
