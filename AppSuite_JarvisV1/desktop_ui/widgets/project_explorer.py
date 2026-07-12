import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem
from desktop_ui.models.project_tree_model import ProjectTreeModel, ProjectNode
from desktop_ui.state.app_state import app_state


class ProjectExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectExplorer")
        
        self.setStyleSheet("""
            QWidget#ProjectExplorer {
                background-color: #1a1a1a;
                border-right: 1px solid #2d2d2d;
            }
            QLabel#ExplorerHeader {
                color: #8c8c8c;
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: 11px;
                padding-left: 8px;
                padding-top: 8px;
                padding-bottom: 8px;
            }
            QTreeWidget {
                background-color: #1a1a1a;
                border: none;
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding-left: 4px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #2d2d2d;
            }
            QTreeWidget::item:selected {
                background-color: #2d2d2d;
                color: #00ff66;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("PROJECT EXPLORER", self)
        header.setObjectName("ExplorerHeader")
        layout.addWidget(header)

        # Tree Widget
        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.itemClicked.connect(self.on_item_clicked)
        
        layout.addWidget(self.tree)

        # Load and populate data
        self.model = ProjectTreeModel()
        self.populate_tree(self.tree.invisibleRootItem(), self.model.root)

    def populate_tree(self, parent_item: QTreeWidgetItem, node: ProjectNode):
        for child in node.children:
            item = QTreeWidgetItem()
            item.setText(0, child.name)
            item.setData(0, Qt.UserRole, child.path)
            
            # Simple icon assignment based on type
            if child.is_dir:
                item.setForeground(0, Qt.white)
                # Expand folder nodes by default
                item.setExpanded(True)
                parent_item.addChild(item)
                self.populate_tree(item, child)
            else:
                item.setForeground(0, Qt.gray)
                parent_item.addChild(item)

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        item_text = item.text(0)
        file_path = item.data(0, Qt.UserRole)
        
        app_state.add_timeline_event(f"Opened file from Explorer: {item_text}")
        
        # Load a file preview if it is a text/json file
        content = f"Inspecting file parameters...\nFile path context: {file_path}"
        if file_path and os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                # If small file, load first 1000 characters
                size = os.path.getsize(file_path)
                if size < 100 * 1024:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read(1000)
                        if len(content) == 1000:
                            content += "\n... [Preview Truncated]"
            except Exception as e:
                content = f"Error reading file preview: {e}"

        # Update inspector diagnostic log
        app_state.update_inspector(
            stage="Project File Review",
            error="None",
            retry_count=0,
            worker="project_explorer",
            stacktrace=content
        )
        app_state.set_active_project(item_text)
