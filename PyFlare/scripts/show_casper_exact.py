import pyzstd
from pathlib import Path

raw = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd").read_bytes()
decomp = pyzstd.decompress(raw[57765888:])

# find "run_scripts /scripts/casper-bottom"
idx = decomp.find(b"run_scripts /scripts/casper-bottom")
print(repr(decomp[idx : idx + 800]))
