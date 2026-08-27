#!/usr/bin/env python3
"""validation/validate_services.py — PyFlare OS validator"""
import os
import sys

import os
import configparser

REQUIRED_SERVICES = [
    'pyflare-engine.service',
    'pyflare-firstrun.service',
    'pyflare-update.service',
    'pyflare-update.timer',
]

def validate(root):
    errors = []
    svc_dir = os.path.join(root, 'filesystem/etc/systemd/system')
    for svc in REQUIRED_SERVICES:
        fp = os.path.join(svc_dir, svc)
        if not os.path.exists(fp):
            errors.append(f"systemd/{svc} missing")
        else:
            c = configparser.ConfigParser(strict=False)
            try:
                c.read(fp)
                if not c.has_section('Unit'):
                    errors.append(f"{svc}: missing [Unit] section")
            except Exception as exc:
                errors.append(f"{svc}: {exc}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_services')
    sys.exit(0 if _ok else 1)
