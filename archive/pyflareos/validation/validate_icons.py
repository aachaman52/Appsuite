#!/usr/bin/env python3
"""validation/validate_icons.py — PyFlare OS validator"""
import os
import sys

import os

def validate(root):
    errors = []
    idx = os.path.join(root, 'filesystem/usr/share/icons/PyFlare-Icons/index.theme')
    if not os.path.exists(idx):
        errors.append('PyFlare-Icons/index.theme missing')
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_icons')
    sys.exit(0 if _ok else 1)
