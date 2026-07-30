#!/usr/bin/env python3
"""validation/validate_boot.py — PyFlare OS validator"""
import os
import sys

import os

REQUIRED_BOOT = [
    'etc/default/grub',
    'etc/plymouth/plymouthd.conf',
    'boot/grub/themes/pyflare/theme.txt',
    'usr/share/plymouth/themes/pyflare/pyflare.plymouth',
    'usr/share/plymouth/themes/pyflare/pyflare.script',
]

def validate(root):
    errors = []
    fs = os.path.join(root, 'filesystem')
    for rel in REQUIRED_BOOT:
        if not os.path.exists(os.path.join(fs, rel)):
            errors.append(f"filesystem/{rel} missing")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_boot')
    sys.exit(0 if _ok else 1)
