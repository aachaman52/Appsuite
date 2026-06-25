"""Initialise the AppSuite SQLite database (idempotent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from appsuite.config import load_config
from appsuite.db import Database


def main() -> None:
    cfg = load_config()
    db = Database(cfg.abs_path("database_path"))
    print(f"Database initialised at {cfg.abs_path('database_path')}")
    db.close()


if __name__ == "__main__":
    main()