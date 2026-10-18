import re
from pathlib import Path

initrd = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
data = initrd.read_bytes()

# Search for the string in initrd
matches = [m.start() for m in re.finditer(b"debconf-communicate fifo", data)]
print("Matches in initrd:", matches)

if matches:
    for idx in matches:
        start = max(0, idx - 200)
        end = min(len(data), idx + 200)
        print("Context:", repr(data[start:end]))
else:
    print("Not found as plain text in initrd directly (might be compressed segment).")
