#!/usr/bin/env python3
"""validation/validate_filesystem.py — PyFlare OS validator"""
import os
import sys

import os

REQUIRED = [
    'etc/hostname', 'etc/os-release', 'etc/fstab', 'etc/hosts',
    'etc/environment', 'etc/default/grub', 'etc/gdm3/custom.conf',
    'etc/systemd/system/pyflare-engine.service',
    'etc/systemd/system/pyflare-firstrun.service',
    'etc/pyflare/os.conf',
    'usr/share/applications',
    'usr/share/glib-2.0/schemas/99-pyflare.gschema.override',
]

def validate(root):
    errors = []
    fs = os.path.join(root, 'filesystem')
    for r in REQUIRED:
        if not os.path.exists(os.path.join(fs, r)):
            errors.append(f"filesystem/{r} missing")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_filesystem')
    sys.exit(0 if _ok else 1)
