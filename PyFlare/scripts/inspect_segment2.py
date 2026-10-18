from pathlib import Path
from parse_initrd import parse_cpio

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()

files, _ = parse_cpio(raw[13275136:])
print(f"Segment 2 has {len(files)} files.")

casper_files = [f for f in files if "casper" in f[0] or "scripts" in f[0] or "debconf" in f[0]]
for f in casper_files:
    print(f[0], f"size={f[1]}")

# If any file has debconf-communicate in its name or content:
for f in files:
    if f[1] > 0 and f[1] < 100000:
        c = raw[13275136 + f[2] : 13275136 + f[2] + f[1]]
        if b"debconf-communicate fifo" in c:
            print("MATCH FOUND IN FILE:", f[0])
            print(c.decode(errors='ignore')[:1000])
