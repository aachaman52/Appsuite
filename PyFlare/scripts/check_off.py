from pathlib import Path

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()

off = 57765888
print("Header at 57765888:", raw[off:off+32].hex(), repr(raw[off:off+32]))
