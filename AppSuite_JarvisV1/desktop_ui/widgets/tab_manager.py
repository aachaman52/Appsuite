from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from desktop_ui.pages.dashboard_page import DashboardPage
from desktop_ui.pages.workers_page import WorkersPage
from desktop_ui.pages.timeline_page import TimelinePage
from desktop_ui.pages.benchmark_page import BenchmarkPage


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
        self.dashboard = DashboardPage(self)
        self.workers = WorkersPage(self)
        self.timeline = TimelinePage(self)
        self.benchmark = BenchmarkPage(self)

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
        
        settings_label = QLabel("Settings Panel (Coming Soon)", self.settings)
        settings_label.setStyleSheet("color: #8c8c8c; font-size: 16px;")
        settings_label.setAlignment(Qt.AlignCenter)
        settings_layout.addWidget(settings_label)

        # 2. Add to TabWidget in exact order corresponding to Sidebar
        self.addTab(self.dashboard, "Dashboard")
        self.addTab(self.workers, "Workers")
        self.addTab(self.timeline, "Timeline")
        self.addTab(self.benchmark, "Benchmark")
        self.addTab(self.assets, "Assets")
        self.addTab(self.settings, "Settings")

    def show_page(self, page_id: str):
        idx = {
            "dashboard": 0,
            "workers": 1,
            "timeline": 2,
            "benchmark": 3,
            "assets": 4,
            "settings": 5
        }.get(page_id, 0)
        self.setCurrentIndex(idx)
