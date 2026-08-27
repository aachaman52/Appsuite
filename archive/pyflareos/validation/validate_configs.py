#!/usr/bin/env python3
"""validation/validate_configs.py — PyFlare OS validator"""
import os
import sys

import os
try:
    import yaml
except ImportError:
    yaml = None

REQUIRED = ['default.yaml', 'packages.yaml', 'theme.yaml', 'branding.yaml', 'post_install.sh']

def validate(root):
    errors = []
    cfg = os.path.join(root, 'config')
    for fname in REQUIRED:
        fp = os.path.join(cfg, fname)
        if not os.path.exists(fp):
            errors.append(f"config/{fname} missing")
        elif yaml and fname.endswith('.yaml'):
            try:
                with open(fp) as fh:
                    yaml.safe_load(fh)
            except Exception as exc:
                errors.append(f"config/{fname}: YAML error: {exc}")
    return len(errors) == 0, errors


if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {_e}')
    print(f'  {"PASS" if _ok else "FAIL"}: validate_configs')
    sys.exit(0 if _ok else 1)
