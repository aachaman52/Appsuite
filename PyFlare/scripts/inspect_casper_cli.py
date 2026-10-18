import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    cmd = "dd if=" + str(td / "casper" / "initrd") + " skip=13275892 iflag=skip_bytes status=none | zstd -d | grep -a -C 3 'overlayfs' || true"
    out = subprocess.check_output(cmd, shell=True, text=True, errors="replace")
    print(out[:2000])
finally:
    subprocess.run(["umount", str(td)], check=True)
