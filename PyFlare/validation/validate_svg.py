#!/usr/bin/env python3
"""validation/validate_svg.py — PyFlare OS validator"""
import os
import sys

import os
import xml.etree.ElementTree as ET

def validate(root):
    errors = []
    skip = {'.git', '__pycache__'}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not fname.endswith('.svg'):
                continue
            fp = os.path.join(dirpath, fname)
            try:
                ET.parse(fp)
            except Exception as exc:
                errors.append(f"{os.path.relpath(fp, root)}: {exc}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_svg')
    sys.exit(0 if _ok else 1)
