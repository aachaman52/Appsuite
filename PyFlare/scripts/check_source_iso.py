import subprocess
import tempfile
import os
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    for root, dirs, files in os.walk(td):
        for f in files:
            if f.endswith((".cfg", ".lst", "info", "size")):
                p = Path(root) / f
                print(f"=== {p.relative_to(td)} ===")
                try:
                    print(p.read_text(encoding="utf-8", errors="replace")[:1000])
                except Exception as e:
                    print(e)
finally:
    subprocess.run(["umount", str(td)], check=True)
