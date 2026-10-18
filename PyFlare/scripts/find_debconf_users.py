import pyzstd
from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
off = 57765888
decompressed = pyzstd.decompress(raw[off:])

files, _ = parse_cpio(decompressed)
for name, size, f_off in files:
    if name.startswith("scripts/casper-bottom/"):
        content = decompressed[f_off : f_off + size]
        if b"casper-preseed" in content or b"debconf" in content or b"confmodule" in content:
            print("Uses debconf/preseed:", name)
