"""AppSuite Desktop — entry point.

Usage:
    python desktop/main.py
    python -m desktop

The backend (appsuite package) runs fully in-process — no HTTP server needed.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# Add PySide6 installed at C:\P6 and the appsuite package to sys.path
_P6 = Path("C:/P6")
if _P6.exists() and str(_P6) not in sys.path:
    sys.path.insert(0, str(_P6))

# Project root (parent of desktop/) — needed so `import desktop.X` works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_APPSUITE_ROOT = _PROJECT_ROOT / "appsuite"
if str(_APPSUITE_ROOT) not in sys.path:
    sys.path.insert(0, str(_APPSUITE_ROOT))

# ── High-DPI support ──────────────────────────────────────────────────────────
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase

from appsuite.config import load_config
from appsuite.main import AppContext
from desktop.app_window import AppWindow


def load_stylesheet(app: QApplication) -> None:
    qss_path = Path(__file__).parent / "styles.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AppSuite Desktop")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("AppSuite")

    # Load and apply theme
    load_stylesheet(app)

    # Boot backend (no uvicorn, no HTTP)
    try:
        config = load_config()
        ctx = AppContext(config)
        ctx.start()
    except Exception as e:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "Startup Error",
            f"Failed to initialise AppSuite backend:\n\n{e}\n\n"
            "Check config/config.json and that all required paths exist.",
        )
        return 1

    window = AppWindow(ctx)
    window.show()

    ret = app.exec()
    return ret


if __name__ == "__main__":
    sys.exit(main())
