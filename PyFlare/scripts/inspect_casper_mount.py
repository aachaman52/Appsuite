import pyzstd

raw = open("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd", "rb").read()
decompressed = pyzstd.decompress(raw[57765888:])

offset = 0
while offset + 110 <= len(decompressed):
    magic = decompressed[offset:offset+6]
    if magic != b"070701" and magic != b"070702":
        break
    header = decompressed[offset:offset+110]
    namesize = int(header[94:102], 16)
    filesize = int(header[54:62], 16)
    hdr_end = offset + 110
    name_raw = decompressed[hdr_end : hdr_end + namesize]
    name = name_raw[:-1].decode(errors="ignore")
    name_pad_len = (4 - ((110 + namesize) % 4)) % 4
    content_start = hdr_end + namesize + name_pad_len
    content = decompressed[content_start : content_start + filesize]
    file_pad_len = (4 - (filesize % 4)) % 4
    next_offset = content_start + filesize + file_pad_len

    if name == "scripts/casper":
        text = content.decode(errors="ignore")
        for line in text.splitlines():
            if "squashfs" in line or "overlay" in line or "layer" in line or "mount_images" in line or "setup_union" in line:
                print(line)
        break
    offset = next_offset
    if name == "TRAILER!!!":
        break
