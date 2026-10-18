import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    res = subprocess.run(["unsquashfs", "-l", str(td / "casper" / "ubuntu-server-minimal.squashfs")], stdout=subprocess.PIPE, text=True)
    lines = [l for l in res.stdout.splitlines() if "graphical.target" in l or "default.target" in l]
    print(f"Total lines: {len(lines)}")
    for l in lines:
        print(l)
finally:
    subprocess.run(["umount", str(td)], check=True)
