import subprocess
from pathlib import Path

sq = "/var/tmp/pyflare_iso_rebuild/iso_content/casper/ubuntu-server-minimal.squashfs"
res = subprocess.run(["unsquashfs", "-l", sq], stdout=subprocess.PIPE, text=True)
files = [l for l in res.stdout.splitlines() if "casper" in l or "initramfs" in l or "debconf" in l]
print(f"Total matching files: {len(files)}")
for f in files:
    if "casper" in f and ("bottom" in f or "script" in f or "fifo" in f or "conf" in f):
        print(" ", f)
