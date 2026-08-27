import sys
from pathlib import Path
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QDockWidget, QApplication, QStyle
)

from desktop_ui.widgets.sidebar import Sidebar
from desktop_ui.widgets.topbar import Topbar
from desktop_ui.widgets.project_explorer import ProjectExplorer
from desktop_ui.widgets.context_inspector import ContextInspector
from desktop_ui.widgets.terminal_panel import TerminalPanel
from desktop_ui.widgets.tab_manager import TabManager
from desktop_ui.widgets.command_palette import CommandPalette
from desktop_ui.state.event_bus import event_bus


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AppSuite Jarvis - AI Engineering Operating System")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)
        
        # Main layout container
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Initialize Widgets
        self.sidebar = Sidebar(self)
        self.topbar = Topbar(self)
        self.tab_manager = TabManager(self)
        self.project_explorer = ProjectExplorer(self)
        self.context_inspector = ContextInspector(self)
        self.terminal_panel = TerminalPanel(self)

        # 2. Main Layout assembly
        # We place sidebar on the extreme left, and a main vertical layout for the rest
        self.main_layout.addWidget(self.sidebar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.topbar)
        
        # Central splitter workspace
        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.addWidget(self.tab_manager)
        content_layout.addWidget(self.workspace_splitter, 1)
        
        self.main_layout.addLayout(content_layout, 1)

        # 3. Create Dockable Panels
        self.setup_docks()

        # 4. Connect Signals and EventBus subscriptions
        self.setup_events()

        # 5. Restore saved window state and geometry
        self.restore_layout()

    def setup_docks(self):
        # Prevent central widget from being completely empty or dock collapsing issues
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AnimatedDocks)

        # Left Dock: Project Explorer
        self.explorer_dock = QDockWidget("Project Explorer", self)
        self.explorer_dock.setObjectName("ExplorerDock")
        self.explorer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.explorer_dock.setWidget(self.project_explorer)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        # Right Dock: Context Inspector
        self.inspector_dock = QDockWidget("Context Inspector", self)
        self.inspector_dock.setObjectName("InspectorDock")
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.inspector_dock.setWidget(self.context_inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        # Bottom Dock: Logs/Terminal Panel
        self.terminal_dock = QDockWidget("Terminal Logs", self)
        self.terminal_dock.setObjectName("TerminalDock")
        self.terminal_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.terminal_dock.setWidget(self.terminal_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_dock)

    def setup_events(self):
        # Event Bus subscriptions
        event_bus.subscribe("NAVIGATE_TO", self.on_remote_navigation)
        
        # Sidebar page selections
        self.sidebar.page_selected.connect(self.switch_workspace_page)
        
        # Topbar search actions
        self.topbar.search_clicked.connect(self.trigger_search)

    def trigger_search(self):
        palette = CommandPalette(self)
        palette.exec()

    def switch_workspace_page(self, page_id: str):
        self.tab_manager.show_page(page_id)

    def on_remote_navigation(self, data: dict):
        page = data.get("page")
        if page:
            self.switch_workspace_page(page)
            self.sidebar.select_page(page)

    def restore_layout(self):
        settings = QSettings("AppSuite", "JarvisV2")
        geom = settings.value("geometry")
        state = settings.value("windowState")
        if geom:
            self.restoreGeometry(geom)
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        settings = QSettings("AppSuite", "JarvisV2")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
