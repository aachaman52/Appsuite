import subprocess
import tempfile
import re
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    with open(str(td / "casper" / "initrd"), "rb") as f:
        data = f.read()

    print(f"Initrd total size: {len(data) / (1024*1024):.2f} MB")
    # Search for compressed stream signatures: zstd (28 b5 2f fd), gzip (1f 8b), lz4 (04 22 4d 18), xz (fd 37 7a 58 5a 00)
    for name, sig in [("zstd", b"\x28\xb5\x2f\xfd"), ("gzip", b"\x1f\x8b"), ("lz4", b"\x04\x22\x4d\x18"), ("xz", b"\xfd7zXZ\x00")]:
        pos = data.find(sig)
        if pos != -1:
            print(f"Found {name} stream at offset {pos} (0x{pos:x})")
finally:
    subprocess.run(["umount", str(td)], check=True)
