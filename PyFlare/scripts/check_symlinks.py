import subprocess
import tempfile
import os
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    ext_dir = Path("/tmp/check_links")
    if ext_dir.exists():
        subprocess.run(["rm", "-rf", str(ext_dir)], check=True)
    subprocess.run(["unsquashfs", "-d", str(ext_dir), str(td / "casper" / "ubuntu-server-minimal.squashfs"), 
                    "etc/systemd/system/default.target", 
                    "etc/systemd/system/display-manager.service",
                    "etc/systemd/system/graphical.target.wants/lightdm.service",
                    "etc/systemd/system/graphical.target.wants/display-manager.service"], check=True)
    for p in ext_dir.glob("etc/systemd/system/**/*"):
        if p.is_symlink():
            print(f"{p.relative_to(ext_dir)} -> {os.readlink(str(p))}")
        elif p.is_file():
            print(f"{p.relative_to(ext_dir)} is file")
finally:
    subprocess.run(["umount", str(td)], check=True)
