#!/usr/bin/env python3
"""validation/validate_theme.py — PyFlare OS validator"""
import os
import sys

import os

REQUIRED_THEME_FILES = [
    'index.theme',
    'gtk-3.0/gtk.css',
    'gtk-4.0/gtk.css',
    'gnome-shell/gnome-shell.css',
]

def validate(root):
    errors = []
    theme = os.path.join(root, 'filesystem/usr/share/themes/PyFlare-Dark')
    if not os.path.isdir(theme):
        return False, ['PyFlare-Dark theme directory missing']
    for rel in REQUIRED_THEME_FILES:
        fp = os.path.join(theme, rel)
        if not os.path.exists(fp):
            errors.append(f"PyFlare-Dark/{rel} missing")
        elif os.path.getsize(fp) < 10:
            errors.append(f"PyFlare-Dark/{rel} is empty")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_theme')
    sys.exit(0 if _ok else 1)
