from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from desktop_ui.pages.dashboard_page import DashboardPage
from desktop_ui.pages.workers_page import WorkersPage
from desktop_ui.pages.timeline_page import TimelinePage


class TabManager(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TabManager")
        
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1a1a1a;
            }
            QTabBar::tab {
                background-color: #212121;
                border: 1px solid #2d2d2d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #8c8c8c;
                padding: 8px 20px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a1a;
                color: #00ff66;
                border-bottom: 2px solid #00ff66;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2d2d2d;
                color: #ffffff;
            }
        """)

        self.setup_ui()

    def setup_ui(self):
        # 1. Instantiate pages
        self.dashboard = DashboardPage(self)
        self.workers = WorkersPage(self)
        self.timeline = TimelinePage(self)

        # Assets Database mock page
        self.assets = QWidget(self)
        self.assets.setObjectName("AssetsPage")
        self.assets.setStyleSheet("background-color: #1a1a1a;")
        assets_layout = QVBoxLayout(self.assets)
        assets_layout.setContentsMargins(24, 24, 24, 24)
        assets_layout.setSpacing(8)
        
        assets_title = QLabel("Assets Database Browser", self.assets)
        assets_title.setStyleSheet("color: #00ff66; font-size: 20px; font-weight: bold;")
        assets_layout.addWidget(assets_title)
        
        assets_desc = QLabel(
            "Browse 3D Meshes, Textures, and Scene templates cached in SQLite database.", 
            self.assets
        )
        assets_desc.setStyleSheet("color: #8c8c8c; font-size: 13px;")
        assets_layout.addWidget(assets_desc)
        assets_layout.addStretch()

        # Settings mock page
        self.settings = QWidget(self)
        self.settings.setObjectName("SettingsPage")
        self.settings.setStyleSheet("background-color: #1a1a1a;")
        settings_layout = QVBoxLayout(self.settings)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(8)
        
        settings_title = QLabel("Application System Settings", self.settings)
        settings_title.setStyleSheet("color: #00ff66; font-size: 20px; font-weight: bold;")
        settings_layout.addWidget(settings_title)
        
        settings_desc = QLabel(
            "Configure AI LLM Providers (OpenAI, Anthropic, Gemini, Local NIM), file paths, and local Godot build settings.", 
            self.settings
        )
        settings_desc.setStyleSheet("color: #8c8c8c; font-size: 13px;")
        settings_layout.addWidget(settings_desc)
        settings_layout.addStretch()

        # 2. Add tabs
        self.addTab(self.dashboard, "Dashboard")
        self.addTab(self.workers, "Workers")
        self.addTab(self.timeline, "Timeline Logs")
        self.addTab(self.assets, "Asset Browser")
        self.addTab(self.settings, "Settings")

    def show_page(self, page_id: str):
        mapping = {
            "dashboard": 0,
            "workers": 1,
            "timeline": 2,
            "assets": 3,
            "settings": 4
        }
        if page_id in mapping:
            self.setCurrentIndex(mapping[page_id])
