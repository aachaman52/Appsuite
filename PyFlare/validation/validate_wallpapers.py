#!/usr/bin/env python3
"""validation/validate_wallpapers.py — PyFlare OS validator"""
import os
import sys

import os

def validate(root):
    errors = []
    bg = os.path.join(root, 'filesystem/usr/share/backgrounds/pyflare')
    if not os.path.isdir(bg):
        errors.append('backgrounds/pyflare/ missing -- run copy_branding.py')
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_wallpapers')
    sys.exit(0 if _ok else 1)
