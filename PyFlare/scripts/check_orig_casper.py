import subprocess
import tempfile
from pathlib import Path

iso = Path("/mnt/c/Users/Aachman_the_great/Desktop/Pyflare/Appsuite/PyFlare/Isos/ubuntu-24.04.4-live-server-amd64.iso")
mnt = Path(tempfile.mkdtemp())
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(mnt)], check=True)
try:
    for p in (mnt / "casper").iterdir():
        print(p.name, f"size={p.stat().st_size} ({p.stat().st_size // (1024*1024)} MB)")
finally:
    subprocess.run(["umount", str(mnt)], check=True)
