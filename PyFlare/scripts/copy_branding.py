#!/usr/bin/env python3
"""
scripts/copy_branding.py
Copy generated branding assets from branding/ into filesystem/ overlay.
Run after: python -m branding_generator.main generate
"""
import os
import shutil
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING = os.path.join(ROOT, "branding")
FS = os.path.join(ROOT, "filesystem")

COPY_MAP = {
    "logos/svg":           "usr/share/icons/PyFlare-Icons/scalable/apps",
    "logos/png":           "usr/share/pixmaps",
    "wallpapers":          "usr/share/backgrounds/pyflare",
    "cursors":             "usr/share/icons/PyFlare",
    "themes/gtk":          "usr/share/themes/PyFlare-Dark/gtk-3.0",
    "fonts":               "usr/share/fonts/pyflare",
}

def main():
    parser = argparse.ArgumentParser(description="Copy branding assets into filesystem overlay")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for src_rel, dst_rel in COPY_MAP.items():
        src = os.path.join(BRANDING, src_rel)
        dst = os.path.join(FS, dst_rel)
        if not os.path.isdir(src):
            print(f"  [skip] {src_rel} — not found")
            continue
        if not args.dry_run:
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(src):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
        print(f"  [copy] {src_rel} -> filesystem/{dst_rel}")

if __name__ == "__main__":
    main()
