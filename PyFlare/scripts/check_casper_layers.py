import subprocess
import tempfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    initrd = td / "casper" / "initrd"
    work = Path("/tmp/check_initrd")
    if work.exists():
        subprocess.run(["rm", "-rf", str(work)], check=True)
    work.mkdir(parents=True, exist_ok=True)
    # unlz4 or cpio or zstd
    # unmkinitramfs extracts all layers of an initrd
    subprocess.run(["unmkinitramfs", str(initrd), str(work)], check=True)
    for p in work.glob("**/scripts/casper*"):
        print(f"Found casper script: {p}")
        text = p.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "overlay" in line.lower() or "squashfs" in line.lower():
                print(f"  {line[:120]}")
finally:
    subprocess.run(["umount", str(td)], check=True)
