import pyzstd
from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()

off = 57765888
decompressed = pyzstd.decompress(raw[off:])
print(f"Decompressed size: {len(decompressed)} bytes ({len(decompressed) // (1024*1024)} MB)")

files, _ = parse_cpio(decompressed)
print(f"Total files in decompressed cpio: {len(files)}")

# Search for debconf-communicate
for name, size, f_off in files:
    if "casper" in name or "debconf" in name:
        print("Casper/Debconf file:", name, f"size={size}")
    if size > 0 and size < 100000:
        c = decompressed[f_off : f_off + size]
        if b"debconf-communicate fifo" in c:
            print(">>> FOUND MATCH IN:", name)
            print(c.decode(errors='ignore')[:1500])
