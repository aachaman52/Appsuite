import struct
import io
import gzip
import lzma
from pathlib import Path

def parse_cpio(data):
    offset = 0
    files = []
    while offset + 110 <= len(data):
        magic = data[offset:offset+6]
        if magic != b"070701" and magic != b"070702":
            break
        namesize = int(data[offset+94:offset+102], 16)
        filesize = int(data[offset+54:offset+62], 16)
        offset += 110
        name = data[offset:offset+namesize-1].decode(errors='ignore')
        offset += namesize
        if offset % 4 != 0:
            offset += (4 - (offset % 4))
        content_offset = offset
        offset += filesize
        if offset % 4 != 0:
            offset += (4 - (offset % 4))
        files.append((name, filesize, content_offset))
        if name == "TRAILER!!!":
            # align to 512 bytes if necessary
            if offset % 512 != 0:
                offset += (512 - (offset % 512))
            return files, offset
    return files, offset

initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
raw = initrd_path.read_bytes()
print(f"Total initrd size: {len(raw)} bytes")

total_offset = 0
segment = 0
while total_offset < len(raw):
    files, next_off = parse_cpio(raw[total_offset:])
    if files:
        print(f"Segment {segment} (uncompressed cpio) at offset {total_offset}: {len(files)} files. Last: {files[-1][0]}")
        total_offset += next_off
        segment += 1
    else:
        print(f"Compressed or unknown data starts at offset {total_offset}")
        break
