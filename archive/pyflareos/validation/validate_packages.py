#!/usr/bin/env python3
"""validation/validate_packages.py — PyFlare OS validator"""
import os
import sys

import os
import json

def validate(root):
    errors = []
    manifests = os.path.join(root, 'packages/manifests')
    if not os.path.isdir(manifests):
        return False, ['packages/manifests/ missing']
    for fname in os.listdir(manifests):
        if not fname.endswith('.json'):
            continue
        fp = os.path.join(manifests, fname)
        try:
            with open(fp) as fh:
                data = json.load(fh)
            if 'schema' not in data:
                errors.append(f"{fname}: missing schema field")
        except Exception as exc:
            errors.append(f"{fname}: {exc}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_packages')
    sys.exit(0 if _ok else 1)
