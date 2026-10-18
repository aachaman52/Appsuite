import pyzstd
from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
off = 57765888
decompressed = pyzstd.decompress(raw[off:])

files, _ = parse_cpio(decompressed)
for name, size, f_off in files:
    content = decompressed[f_off : f_off + size]
    if b"Loading essential drivers" in content:
        print("Found in:", name)
        idx = content.find(b"Loading essential drivers")
        print(content[idx-100 : idx+500].decode(errors='ignore'))
