import subprocess
import tempfile
from pathlib import Path

iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
if not iso.exists():
    iso = Path("/mnt/c/Users/Aachman_the_great/Desktop/Appsuite-1/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")

mnt = Path(tempfile.mkdtemp())
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(mnt)], check=True)
try:
    for p in mnt.rglob("*.cfg"):
        print("=== File:", p.relative_to(mnt), "===")
        print(p.read_text(errors='ignore')[:1500])
finally:
    subprocess.run(["umount", str(mnt)], check=True)
