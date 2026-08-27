#!/usr/bin/env python3
"""validation/validate_json.py — PyFlare OS validator"""
import os
import sys

import os
import json

def validate(root):
    errors = []
    skip = {'.git', 'node_modules', '__pycache__', 'branding'}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not fname.endswith('.json'):
                continue
            fp = os.path.join(dirpath, fname)
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    json.load(fh)
            except Exception as exc:
                errors.append(f"{os.path.relpath(fp, root)}: {exc}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_json')
    sys.exit(0 if _ok else 1)
