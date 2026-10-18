import pyzstd
import time
from pathlib import Path
from parse_initrd import parse_cpio

t0 = time.time()
initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
off = 57765888
prefix = raw[:off]
compressed = raw[off:]

decompressed = pyzstd.decompress(compressed)
files, _ = parse_cpio(decompressed)
print(f"Total files in cpio: {len(files)}")

def make_cpio_entry(path, content, mode=0o100755):
    name_bytes = path.encode('utf-8') + b'\x00'
    namesize = len(name_bytes)
    filesize = len(content)
    hdr = f"070701{1:08x}{mode:08x}{0:08x}{0:08x}{1:08x}{0:08x}{filesize:08x}{0:08x}{0:08x}{0:08x}{0:08x}{namesize:08x}{0:08x}".encode('ascii')
    pad1 = b'\x00' * ((4 - ((110 + namesize) % 4)) % 4)
    pad2 = b'\x00' * ((4 - (filesize % 4)) % 4)
    return hdr + name_bytes + pad1 + content + pad2

# Rebuild cpio
out_cpio = bytearray()
replaced = False

for name, size, f_off in files:
    if name == "TRAILER!!!":
        continue
    content = decompressed[f_off : f_off + size]
    # Check mode from original header
    # Header starts at (f_off - namesize - pads - 110)
    # But mode is at header offset 14 (8 chars hex)
    # For safety, parse mode:
    # Let's find header
    if name == "scripts/casper":
        text = content.decode(errors='ignore')
        target = 'log_begin_msg "Creating debconf-communicate fifo mechanism"\n    mkfifo /tmp/debconf-in.fifo\n    mkfifo /tmp/debconf-out.fifo'
        replacement = 'log_begin_msg "Creating debconf-communicate fifo mechanism"\n    mkfifo /tmp/debconf-in.fifo\n    mkfifo /tmp/debconf-out.fifo\n    exec 3<>/tmp/debconf-in.fifo\n    exec 4<>/tmp/debconf-out.fifo'
        assert target in text, "Target not in scripts/casper"
        content = text.replace(target, replacement, 1).encode('utf-8')
        replaced = True
        print("Replaced in scripts/casper! New size:", len(content))
    out_cpio.extend(make_cpio_entry(name, content))

assert replaced, "scripts/casper was not replaced"
out_cpio.extend(make_cpio_entry("TRAILER!!!", b"", mode=0))

# Pad to 512 bytes
pad_final = (512 - (len(out_cpio) % 512)) % 512
out_cpio.extend(b'\x00' * pad_final)

print(f"Reconstructed cpio: {len(out_cpio)} bytes ({len(out_cpio)//(1024*1024)} MB)")
t1 = time.time()
recompressed = pyzstd.compress(bytes(out_cpio), level_or_option=3)
print(f"Recompressed with pyzstd to {len(recompressed)} bytes ({len(recompressed)//(1024*1024)} MB) in {time.time()-t1:.2f}s")

new_initrd = prefix + recompressed
print(f"Total new initrd: {len(new_initrd)} bytes in {time.time()-t0:.2f}s")
