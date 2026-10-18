from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
print(f"Total size: {len(raw)}")

# Parse segment 2
files2, off2 = parse_cpio(raw[13275136:])
print(f"Segment 2 files: {len(files2)}")
if files2:
    print(f"First file: {files2[0][0]}, Last file: {files2[-1][0]}")

# Parse segment 3 (zstd)
import pyzstd
try:
    decomp = pyzstd.decompress(raw[57765888:])
    files3, _ = parse_cpio(decomp)
    print(f"Segment 3 decompressed files: {len(files3)}")
except Exception as e:
    print(f"Error in segment 3: {e}")
