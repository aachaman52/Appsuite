#!/usr/bin/env python3
"""
scripts/prepare_rootfs.py
Prepares the rootfs overlay for injection into the Ubuntu base squashfs.
Runs before mksquashfs.
"""
import os
import shutil
import subprocess

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FS_SRC = os.path.join(ROOT, "filesystem")
BUILD  = os.path.join(ROOT, "build", "rootfs-overlay")

def main():
    print("[prepare_rootfs] Building rootfs overlay...")
    if os.path.exists(BUILD):
        shutil.rmtree(BUILD)
    shutil.copytree(FS_SRC, BUILD, symlinks=True)

    # Remove placeholder .keep files
    for dirpath, _, files in os.walk(BUILD):
        for f in files:
            if f in (".keep", "README.md"):
                os.remove(os.path.join(dirpath, f))

    # Copy branding assets
    subprocess.run(["python", "scripts/copy_branding.py"], cwd=ROOT, check=True)

    # Package apps
    subprocess.run(["python", "scripts/package_apps.py"], cwd=ROOT, check=True)

    print(f"[prepare_rootfs] Done -> {BUILD}")

if __name__ == "__main__":
    main()
