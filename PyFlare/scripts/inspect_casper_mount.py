import subprocess
import tempfile
import zstandard as zstd
import io
import tarfile
from pathlib import Path

td = Path(tempfile.mkdtemp())
iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
subprocess.run(["mount", "-o", "loop,ro", str(iso), str(td)], check=True)
try:
    with open(str(td / "casper" / "initrd"), "rb") as f:
        f.seek(13275892)
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f) as reader:
            decompressed = reader.read(50 * 1024 * 1024) # read first 50MB of cpio
            print(f"Decompressed {len(decompressed)} bytes of cpio!")
            # Search for casper script in the cpio bytes
            pos = 0
            while True:
                idx = decompressed.find(b"overlay", pos)
                if idx == -1:
                    break
                snippet = decompressed[max(0, idx - 100):min(len(decompressed), idx + 200)]
                try:
                    s = snippet.decode('utf-8', errors='ignore')
                    if "mount" in s and ("squashfs" in s or "overlay" in s):
                        print("=== Match ===")
                        print(s)
                except Exception:
                    pass
                pos = idx + 100
                if pos > len(decompressed) - 200:
                    break
finally:
    subprocess.run(["umount", str(td)], check=True)
