from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QScrollArea
from desktop_ui.state.event_bus import event_bus
from desktop_ui.state.app_state import app_state


class ContextInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContextInspector")
        
        self.setStyleSheet("""
            QWidget#ContextInspector {
                background-color: #1a1a1a;
                border-left: 1px solid #2d2d2d;
            }
            QLabel#InspectorHeader {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: 11px;
                padding-left: 8px;
                padding-top: 8px;
                padding-bottom: 8px;
            }
            QLabel.PropLabel {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: bold;
            }
            QLabel.PropValue {
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QTextEdit {
                background-color: #151515;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
                color: #a9b7c6;
                font-family: 'Consolas';
                font-size: 10px;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QLabel("CONTEXT INSPECTOR", self)
        header.setObjectName("InspectorHeader")
        layout.addWidget(header)

        # Scroll Area for properties to fit long text
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(6)

        # Properties
        self.lbl_worker = self.create_property(scroll_layout, "Active Worker", "None")
        self.lbl_stage = self.create_property(scroll_layout, "Current Stage", "None")
        self.lbl_retries = self.create_property(scroll_layout, "Retry Count", "0")
        self.lbl_error = self.create_property(scroll_layout, "Active Error", "None", is_error=True)
        
        # LLM Reasoning Summary
        self.lbl_reasoning = self.create_property(scroll_layout, "Reasoning Summary", "None")
        
        # Used Assets
        self.lbl_used_assets = self.create_property(scroll_layout, "Used Assets", "None")
        
        # Generated Files
        self.lbl_gen_files = self.create_property(scroll_layout, "Generated Files", "None")

        # Stacktrace field header
        st_header = QLabel("Diagnostic Log / Stacktrace:", scroll_content)
        st_header.setStyleSheet("color: #8c8c8c; font-weight: bold; font-size: 11px; margin-top: 6px;")
        scroll_layout.addWidget(st_header)

        # Stacktrace field
        self.txt_stack = QTextEdit(scroll_content)
        self.txt_stack.setReadOnly(True)
        self.txt_stack.setMinimumHeight(150)
        self.txt_stack.setPlainText("Select a task or log line to inspect trace details.")
        scroll_layout.addWidget(self.txt_stack)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Connect to EventBus updates
        event_bus.subscribe("INSPECTOR_UPDATED", self.on_inspector_update)

    def create_property(self, parent_layout, label: str, val: str, is_error: bool = False) -> QLabel:
        row = QWidget(self)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 2)
        row_layout.setSpacing(2)

        lbl = QLabel(f"{label}", row)
        lbl.className = "PropLabel"
        lbl.setStyleSheet("color: #8c8c8c; font-size: 11px; font-weight: bold;")
        row_layout.addWidget(lbl)

        val_lbl = QLabel(val, row)
        val_lbl.setWordWrap(True)
        val_lbl.className = "PropValue"
        fg_color = "#ff3333" if is_error else "#ffffff"
        val_lbl.setStyleSheet(f"color: {fg_color}; font-size: 11px;")
        row_layout.addWidget(val_lbl)

        parent_layout.addWidget(row)
        return val_lbl

    def on_inspector_update(self, data: dict):
        self.lbl_stage.setText(data.get("stage", "None"))
        self.lbl_worker.setText(data.get("worker", "None"))
        self.lbl_retries.setText(str(data.get("retry_count", 0)))
        
        error_text = data.get("error", "None")
        self.lbl_error.setText(error_text)
        if error_text != "None":
            self.lbl_error.setStyleSheet("color: #ff3333; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_error.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 11px;")
            
        self.lbl_reasoning.setText(data.get("reasoning", "None"))
        self.lbl_used_assets.setText(data.get("used_assets", "None"))
        self.lbl_gen_files.setText(data.get("gen_files", "None"))
        self.txt_stack.setPlainText(data.get("stacktrace", ""))
