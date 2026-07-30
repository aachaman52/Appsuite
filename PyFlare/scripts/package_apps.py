#!/usr/bin/env python3
"""
scripts/package_apps.py
Package application stubs into the filesystem overlay.
Copies applications/{slug}/src/ -> filesystem/opt/pyflare/apps/{slug}/
"""
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(ROOT, "applications")
DEST = os.path.join(ROOT, "filesystem", "opt", "pyflare", "apps")

def main():
    os.makedirs(DEST, exist_ok=True)
    for slug in os.listdir(APPS):
        src_dir = os.path.join(APPS, slug, "src")
        if not os.path.isdir(src_dir):
            continue
        dst_dir = os.path.join(DEST, slug)
        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        print(f"  [pack] applications/{slug}/src -> filesystem/opt/pyflare/apps/{slug}")

if __name__ == "__main__":
    main()
