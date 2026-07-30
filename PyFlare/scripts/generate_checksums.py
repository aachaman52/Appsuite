#!/usr/bin/env python3
"""
scripts/generate_checksums.py
Generate SHA256SUMS and MD5SUMS for the output/ directory.
"""
import os
import hashlib

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")

def hash_file(path, algo="sha256"):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    if not os.path.isdir(OUTPUT):
        print("output/ not found — build ISO first.")
        return
    for fname in os.listdir(OUTPUT):
        fp = os.path.join(OUTPUT, fname)
        if not os.path.isfile(fp):
            continue
        sha = hash_file(fp, "sha256")
        md5 = hash_file(fp, "md5")
        print(f"{sha}  {fname}")
        with open(fp + ".sha256", "w") as f:
            f.write(f"{sha}  {fname}\n")
        with open(fp + ".md5", "w") as f:
            f.write(f"{md5}  {fname}\n")

if __name__ == "__main__":
    main()
