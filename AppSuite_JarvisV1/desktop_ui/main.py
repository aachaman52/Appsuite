import sys
import os
import subprocess
from pathlib import Path

# Relaunch detection if PySide6 is missing from current environment
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    if os.name == "nt":
        print("[AppSuite Desktop UI] PySide6 not found on default python. Attempting to relaunch with py -3.12...")
        try:
            res = subprocess.run(["py", "-3.12", "-c", "import PySide6"], capture_output=True)
            if res.returncode == 0:
                argv = ["py", "-3.12"] + sys.argv
                sys.exit(subprocess.call(argv))
        except Exception:
            pass
    print("[AppSuite Desktop UI] Error: PySide6 is not installed on this python environment.")
    sys.exit(1)

# Add project root directory to path to support imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from desktop_ui.app_window import AppWindow

from desktop_ui.state.app_state import app_state

def main():
    print("[AppSuite Desktop UI] Starting PySide6 application shell...")
    app = QApplication(sys.argv)
    
    # Load stylesheet if exists
    qss_path = Path(__file__).resolve().parent / "styles.qss"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            
    # Bootstrap AppSuite backend context and supervisor
    app_state.bootstrap()
            
    window = AppWindow()
    window.show()
    
    exit_code = app.exec()
    app_state.shutdown()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
