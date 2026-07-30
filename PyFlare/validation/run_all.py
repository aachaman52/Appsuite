#!/usr/bin/env python3
"""
validation/run_all.py
Run every PyFlare OS validator and report pass/fail.
"""
import sys
import importlib
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VALIDATORS = [
    ("validate_branding",       "Branding assets"),
    ("validate_icons",          "Icon theme"),
    ("validate_wallpapers",     "Wallpapers"),
    ("validate_json",           "JSON files"),
    ("validate_svg",            "SVG files"),
    ("validate_desktop",        "Desktop entries"),
    ("validate_packages",       "Package manifests"),
    ("validate_filesystem",     "Filesystem overlay"),
    ("validate_theme",          "GTK/GNOME theme"),
    ("validate_configs",        "Config files"),
    ("validate_services",       "Systemd services"),
    ("validate_permissions",    "File permissions"),
    ("validate_desktop_entries","Desktop entry syntax"),
    ("validate_boot",           "Boot configuration"),
]

def run():
    passed = failed = 0
    report = []
    print("\n  PyFlare OS — Validation Suite")
    print("  " + "=" * 50)
    for mod_name, label in VALIDATORS:
        t0 = time.perf_counter()
        try:
            mod = importlib.import_module(f"validation.{mod_name}")
            ok, errors = mod.validate(ROOT)
        except Exception as e:
            ok, errors = False, [str(e)]
        elapsed = time.perf_counter() - t0
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status}  {label:<35} {elapsed:.2f}s")
        if not ok:
            for e in errors[:5]:
                print(f"         -> {e}")
            failed += 1
        else:
            passed += 1
        report.append({"validator": mod_name, "passed": ok, "errors": errors})

    print("  " + "=" * 50)
    print(f"  Result: {passed} passed, {failed} failed\n")

    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    import json
    with open(os.path.join(ROOT, "reports", "validation.json"), "w") as f:
        json.dump(report, f, indent=2)

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(run())
