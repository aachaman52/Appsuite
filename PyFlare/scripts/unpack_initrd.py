import subprocess
import os
from pathlib import Path

tmp = Path("/tmp/initrd_inspect")
tmp.mkdir(parents=True, exist_ok=True)
initrd = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")

# Check cpio contents
p = subprocess.run(["cpio", "-idmv"], input=initrd.read_bytes(), cwd=tmp, capture_output=True)
print("Return code:", p.returncode)
print("Stdout:", p.stdout.decode(errors='ignore')[:500])
print("Stderr:", p.stderr.decode(errors='ignore')[:500])
