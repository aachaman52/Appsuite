import subprocess
from pathlib import Path

initrd = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
data = initrd.read_bytes()

offset = 13275892
zstd_data = data[offset:]

p = subprocess.run(["zstd", "-d"], input=zstd_data, capture_output=True)
print("Decompressed size:", len(p.stdout))
if p.stdout:
    # search for debconf-communicate
    idx = p.stdout.find(b"debconf-communicate fifo")
    print("Found 'debconf-communicate fifo' at:", idx)
    if idx != -1:
        start = max(0, idx - 400)
        end = min(len(p.stdout), idx + 400)
        print("Context in initramfs:\n", p.stdout[start:end].decode(errors='ignore'))
