#!/usr/bin/env python3
"""
Package Manager — entry point
dev.pyflare.PackageManager
Aachman Studios / PyFlare OS 1.0.0
"""

import sys
import os

APP_ID      = "dev.pyflare.PackageManager"
APP_NAME    = "Package Manager"
APP_VERSION = "1.0.0"


def main() -> int:
    print(f"{APP_NAME} {APP_VERSION} starting...")
    # TODO: initialise GTK / application loop
    return 0


if __name__ == "__main__":
    sys.exit(main())
