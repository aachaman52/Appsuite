import subprocess
import sys
from pathlib import Path

# Check if debconf-communicate is mentioned in overlay
overlay = Path("/var/tmp/pyflare_iso_rebuild/overlay")
p = subprocess.run(["grep", "-rn", "debconf-communicate", str(overlay)], capture_output=True, text=True)
print("Overlay matches:", p.stdout[:500])

# Let's see if unsquashfs can search or list files in dst_base_sq
base_sq = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/ubuntu-server-minimal.squashfs")
p2 = subprocess.run(["unsquashfs", "-l", str(base_sq)], capture_output=True, text=True)
lines = [l for l in p2.stdout.splitlines() if "casper" in l or "debconf" in l]
print(f"Total matching lines in base squashfs: {len(lines)}")
for l in lines[:30]:
    print(" ", l)
