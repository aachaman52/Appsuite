import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    res = subprocess.run(["unsquashfs", "-l", str(td / "casper" / "ubuntu-server-minimal.squashfs")], stdout=subprocess.PIPE, text=True)
    matches = [l for l in res.stdout.splitlines() if "gdm3" in l and ("bin" in l or "sbin" in l or "service" in l)]
    print(f"Total gdm3 matches: {len(matches)}")
    for m in matches[:15]:
        print(" ", m)
finally:
    subprocess.run(["umount", str(td)], check=True)
