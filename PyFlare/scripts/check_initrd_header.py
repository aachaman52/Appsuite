import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    with open(str(td / "casper" / "initrd"), "rb") as f:
        data = f.read(1024)
        print("Initrd header:", data[:16].hex(), repr(data[:16]))
finally:
    subprocess.run(["umount", str(td)], check=True)
