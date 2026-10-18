import pyzstd
import time
from pathlib import Path
from parse_initrd import parse_cpio

t0 = time.time()
initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
print(f"Read initrd ({len(raw)} bytes) in {time.time()-t0:.2f}s")

off = 57765888
prefix = raw[:off]
compressed = raw[off:]

t1 = time.time()
decompressed = pyzstd.decompress(compressed)
print(f"Decompressed {len(decompressed)} bytes in {time.time()-t1:.2f}s")

# Let's inspect the exact lines to replace in scripts/casper
target = b"""    log_begin_msg "Creating debconf-communicate fifo mechanism"
    mkfifo /tmp/debconf-in.fifo
    mkfifo /tmp/debconf-out.fifo"""

replacement = b"""    log_begin_msg "Creating debconf-communicate fifo mechanism"
    mkfifo /tmp/debconf-in.fifo
    mkfifo /tmp/debconf-out.fifo
    exec 3<>/tmp/debconf-in.fifo
    exec 4<>/tmp/debconf-out.fifo"""

assert target in decompressed, "Target string not found in decompressed initrd!"
new_decompressed = decompressed.replace(target, replacement, 1)
print(f"Patched scripts/casper successfully! Len diff: {len(new_decompressed) - len(decompressed)}")

# Re-align cpio if needed?
# In cpio, filesize and namesize are in the 110-byte header of scripts/casper!
# Ah! In cpio newc archive, each file has its filesize in the header!
# If we change the size of scripts/casper, we must update the cpio header filesize!
