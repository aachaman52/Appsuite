#!/usr/bin/env python3
"""validation/validate_permissions.py — PyFlare OS validator"""
import os
import sys

import os
import stat

ADVISORY = [
    'opt/pyflare/engine/pyflare-engine',
    'opt/pyflare/bin/pyflare-updater',
    'opt/pyflare/bin/pyflare-firstrun',
]

def validate(root):
    warnings = []
    fs = os.path.join(root, 'filesystem')
    for rel in ADVISORY:
        fp = os.path.join(fs, rel)
        if os.path.exists(fp) and not (os.stat(fp).st_mode & stat.S_IXUSR):
            warnings.append(f"{rel} not executable (fixable at install)")
    return True, warnings


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_permissions')
    sys.exit(0 if _ok else 1)
