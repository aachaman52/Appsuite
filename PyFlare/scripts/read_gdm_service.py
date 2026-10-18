import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    ext_dir = Path("/tmp/check_gdm_svc")
    if ext_dir.exists():
        subprocess.run(["rm", "-rf", str(ext_dir)], check=True)
    subprocess.run(["unsquashfs", "-d", str(ext_dir), str(td / "casper" / "ubuntu-server-minimal.squashfs"), 
                    "usr/lib/systemd/system/gdm3.service"], check=True)
    svc_file = ext_dir / "usr" / "lib" / "systemd" / "system" / "gdm3.service"
    print(svc_file.read_text())
finally:
    subprocess.run(["umount", str(td)], check=True)
