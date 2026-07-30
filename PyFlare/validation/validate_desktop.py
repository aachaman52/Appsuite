#!/usr/bin/env python3
"""validation/validate_desktop.py — PyFlare OS validator"""
import os
import sys

import os

REQUIRED_KEYS = ['Type', 'Name', 'Exec', 'Icon']

def validate(root):
    errors = []
    apps_dir = os.path.join(root, 'filesystem/usr/share/applications')
    if not os.path.isdir(apps_dir):
        return False, ['filesystem/usr/share/applications/ missing']
    for fname in os.listdir(apps_dir):
        if not fname.endswith('.desktop'):
            continue
        fp = os.path.join(apps_dir, fname)
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
        for key in REQUIRED_KEYS:
            if f'{key}=' not in content:
                errors.append(f"{fname}: missing {key}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_desktop')
    sys.exit(0 if _ok else 1)
