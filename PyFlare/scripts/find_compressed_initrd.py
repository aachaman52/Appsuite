import gzip
import lzma
from pathlib import Path

initrd = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
data = initrd.read_bytes()

# Look for compression magic bytes:
# zstd: 28 b5 2f fd
# gzip: 1f 8b
# xz:   fd 37 7a 58 5a 00
# lz4:  04 22 4d 18

for name, magic in [
    ("zstd", b"\x28\xb5\x2f\xfd"),
    ("gzip", b"\x1f\x8b"),
    ("xz", b"\xfd\x37\x7a\x58\x5a\x00"),
    ("lz4", b"\x04\x22\x4d\x18"),
]:
    pos = 0
    found = []
    while True:
        idx = data.find(magic, pos)
        if idx == -1:
            break
        found.append(idx)
        pos = idx + len(magic)
    print(f"Magic {name}: found at {found[:10]}")
