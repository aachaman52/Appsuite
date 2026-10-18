import pyzstd
from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
off = 57765888
decompressed = pyzstd.decompress(raw[off:])

files, _ = parse_cpio(decompressed)
for name, size, f_off in files:
    if name == "scripts/casper":
        content = decompressed[f_off : f_off + size].decode(errors='ignore')
        idx = content.find("Creating debconf-communicate fifo mechanism")
        print("=== 50 lines before ===")
        print(content[idx-1500 : idx])
        print("=== 50 lines after ===")
        print(content[idx : idx+1500])
