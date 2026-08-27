#!/usr/bin/env python3
"""validation/validate_branding.py — PyFlare OS validator"""
import os
import sys

import os

def validate(root):
    errors = []
    branding = os.path.join(root, 'branding')
    if not os.path.isdir(branding):
        return False, ['branding/ directory missing']
    required = ['logos/svg', 'wallpapers', 'cursors', 'badges', 'previews']
    for r in required:
        if not os.path.isdir(os.path.join(branding, r)):
            errors.append(f'Missing branding/{r}/')
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_branding')
    sys.exit(0 if _ok else 1)
