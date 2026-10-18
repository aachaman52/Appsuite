import subprocess
import tempfile
from pathlib import Path

iso = Path("/mnt/c/Users/Aachman_the_great/Desktop/Pyflare/Appsuite/PyFlare/Isos/ubuntu-24.04.4-live-server-amd64.iso")
mnt = Path(tempfile.mkdtemp())
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(mnt)], check=True)
try:
    for p in mnt.rglob("*.cfg"):
        print("=== File:", p.relative_to(mnt), "===")
        print(p.read_text(errors='ignore')[:1500])
finally:
    subprocess.run(["umount", str(mnt)], check=True)
