import subprocess
import tempfile
import os
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    ext_dir = Path("/tmp/check_gdm_all")
    if ext_dir.exists():
        subprocess.run(["rm", "-rf", str(ext_dir)], check=True)
    subprocess.run(["unsquashfs", "-d", str(ext_dir), str(td / "casper" / "ubuntu-server-minimal.squashfs"), 
                    "usr/lib/systemd/system/gdm.service",
                    "usr/lib/systemd/system/gdm3.service"], check=True)
    for p in ext_dir.glob("**/*"):
        if p.is_symlink():
            print(f"SYMLINK: {p} -> {os.readlink(str(p))}")
        elif p.is_file():
            print(f"FILE: {p} (size {p.stat().st_size})")
finally:
    subprocess.run(["umount", str(td)], check=True)
