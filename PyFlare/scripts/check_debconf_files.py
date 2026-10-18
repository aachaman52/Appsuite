import subprocess
from pathlib import Path

base_sq = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/ubuntu-server-minimal.squashfs")
overlay_sq = Path("/var/tmp/pyflare_iso_rebuild/overlay.squashfs")

p = subprocess.run(["unsquashfs", "-l", str(base_sq)], capture_output=True, text=True)
for item in [
    "etc/debconf.conf",
    "var/cache/debconf/config.dat",
    "var/cache/debconf/passwords.dat",
    "var/cache/debconf/templates.dat",
    "usr/bin/debconf-communicate",
]:
    matches = [l for l in p.stdout.splitlines() if item in l]
    print(f"{item} in base_sq: {len(matches)}")
    if matches:
        print(" ", matches[0])
