#!/usr/bin/env python3
"""validation/validate_desktop_entries.py — PyFlare OS validator"""
import os
import sys

import os

DESKTOP_APP_IDS = [
    'dev.pyflare.Engine', 'dev.pyflare.AppSuite', 'dev.pyflare.Terminal',
    'dev.pyflare.Browser', 'dev.pyflare.Files', 'dev.pyflare.Store',
    'dev.pyflare.Settings', 'dev.pyflare.PackageManager',
    'dev.pyflare.PluginManager', 'dev.pyflare.Launcher', 'dev.pyflare.AIAssistant',
]

def validate(root):
    errors = []
    apps_dir = os.path.join(root, 'filesystem/usr/share/applications')
    for app_id in DESKTOP_APP_IDS:
        fp = os.path.join(apps_dir, f'{app_id}.desktop')
        if not os.path.exists(fp):
            errors.append(f'{app_id}.desktop missing')
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_desktop_entries')
    sys.exit(0 if _ok else 1)
