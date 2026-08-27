#!/usr/bin/env python3
"""
scripts/generate_manifest.py
Generate a complete file manifest for the filesystem/ overlay.
Outputs: reports/filesystem_manifest.json
"""
import os
import json
import hashlib
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FS   = os.path.join(ROOT, "filesystem")
OUT  = os.path.join(ROOT, "reports", "filesystem_manifest.json")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    files = {}
    for dirpath, _, filenames in os.walk(FS):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            rel = os.path.relpath(fp, FS)
            files[rel] = {
                "size": os.path.getsize(fp),
                "sha256": sha256(fp),
                "mtime": os.path.getmtime(fp),
            }
    manifest = {
        "generated": datetime.utcnow().isoformat(),
        "root": "filesystem/",
        "file_count": len(files),
        "files": files,
    }
    with open(OUT, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest: {len(files)} files -> {OUT}")

if __name__ == "__main__":
    main()
