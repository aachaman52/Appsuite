import pyzstd
from pathlib import Path

def patch_initrd_file(initrd_path: Path) -> bytes:
    raw = initrd_path.read_bytes()
    off = 57765888
    prefix = raw[:off]
    compressed = raw[off:]

    decompressed = pyzstd.decompress(compressed)

    offset = 0
    new_cpio = bytearray()
    patched_casper = False
    patched_functions = False
    patched_adduser = False
    patched_preseed = False
    patched_selections = False
    patched_modules = False

    while offset + 110 <= len(decompressed):
        magic = decompressed[offset:offset+6]
        if magic != b"070701" and magic != b"070702":
            new_cpio.extend(decompressed[offset:])
            break

        header = decompressed[offset:offset+110]
        namesize = int(header[94:102], 16)
        filesize = int(header[54:62], 16)
        hdr_end = offset + 110
        name_raw = decompressed[hdr_end : hdr_end + namesize]
        name = name_raw[:-1].decode(errors='ignore')
        
        name_pad_len = (4 - ((110 + namesize) % 4)) % 4
        content_start = hdr_end + namesize + name_pad_len
        content = decompressed[content_start : content_start + filesize]
        file_pad_len = (4 - (filesize % 4)) % 4
        next_offset = content_start + filesize + file_pad_len

        if name == "scripts/casper":
            text = content.decode('utf-8', errors='ignore')
            # 1. Neutralize debconf fifo block
            idx1 = text.find('log_begin_msg "Creating debconf-communicate fifo mechanism"')
            idx2 = text.find('exec 4</tmp/debconf-out.fifo 3>/tmp/debconf-in.fifo')
            if idx1 != -1 and idx2 != -1:
                end_block = idx2 + len('exec 4</tmp/debconf-out.fifo 3>/tmp/debconf-in.fifo')
                text = text[:idx1] + 'log_begin_msg "Creating debconf-communicate fifo mechanism"\n    log_end_msg' + text[end_block:]
                patched_casper = True
            elif 'exec 4</tmp/debconf-out.fifo' not in text:
                patched_casper = True

            # 2. Neutralize the wait $debconfpid and debconf-copydb block!
            target_cleanup = '    # Close the fd\'s associated with debconf-communicate.\n    exec 3>&- 4<&-\n    rm -f /tmp/debconf-in.fifo\n    rm -f /tmp/debconf-out.fifo\n    wait $debconfpid\n\n    # Copy config database changes back to the master files.\n    chroot /root debconf-copydb tmpdb config \\\n        --config=Name:tmpdb --config=Driver:File \\\n        --config="Filename:$DEBCONF_TMPDIR/config.dat"\n    chroot /root debconf-copydb tmpdb passwords \\\n        --config=Name:tmpdb --config=Driver:File \\\n        --config="Filename:$DEBCONF_TMPDIR/passwords.dat"\n    rm -rf "$DEBCONF_TMPDIR"'
            replacement_cleanup = '    # Close the fd\'s associated with debconf-communicate.\n    rm -f /tmp/debconf-in.fifo /tmp/debconf-out.fifo\n    [ -n "$debconfpid" ] && wait "$debconfpid" 2>/dev/null || true'
            
            if target_cleanup in text:
                text = text.replace(target_cleanup, replacement_cleanup, 1)
                print("Replaced target_cleanup successfully in scripts/casper!")
            elif 'wait $debconfpid' not in text:
                print("target_cleanup was already replaced or absent.")

            new_content = text.encode('utf-8')
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            offset = next_offset
            continue

        elif name == "scripts/casper-functions":
            text = content.decode('utf-8', errors='ignore')
            target_lcm = """load_confmodule() {
\t# Only do this once.
\tif [ -z "$DEBCONF_REDIR" ]; then
\t\texec <&4
\t\texport DEBIAN_HAS_FRONTEND=1
\t\texport DEBCONF_REDIR=1
\tfi

\t. /root/usr/share/debconf/confmodule
}"""
            replacement_lcm = """load_confmodule() {
\texport DEBIAN_HAS_FRONTEND=1
\texport DEBCONF_REDIR=1
\tdb_get() { RET=""; return 0; }
\tdb_set() { return 0; }
\tdb_input() { return 0; }
\tdb_go() { return 0; }
\tdb_register() { return 0; }
\tdb_unregister() { return 0; }
\tdb_fget() { RET=""; return 0; }
\tdb_fset() { return 0; }
\tdb_stop() { return 0; }
\tdb_reset() { return 0; }
\tdb_subst() { return 0; }
\tdb_progress() { return 0; }
\tdb_capb() { return 0; }
\tdb_title() { return 0; }
\treturn 0
}"""
            if target_lcm in text:
                text = text.replace(target_lcm, replacement_lcm, 1)
                patched_functions = True
            elif "db_get() { RET=\"\"; return 0; }" in text:
                patched_functions = True
            else:
                # Fallback: replace any load_confmodule block
                idx = text.find("load_confmodule() {")
                if idx != -1:
                    end_idx = text.find("}", idx)
                    if end_idx != -1:
                        text = text[:idx] + replacement_lcm + text[end_idx+1:]
                        patched_functions = True

            new_content = text.encode('utf-8')
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            offset = next_offset
            continue

        elif name == "scripts/casper-bottom/25adduser":
            new_content = b"""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case $1 in prereqs) prereqs; exit 0 ;; esac

. /scripts/casper-functions
log_begin_msg "Setting up user permissions"
if [ -d /root/etc/sudoers.d ]; then
    echo "pyflare ALL=(ALL) NOPASSWD: ALL" > /root/etc/sudoers.d/casper
    chmod 0440 /root/etc/sudoers.d/casper
fi
chroot /root chown -R 1000:1000 /home/pyflare 2>/dev/null || true
log_end_msg
exit 0
"""
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            patched_adduser = True
            offset = next_offset
            continue

        elif name in ("scripts/casper-bottom/24preseed", "scripts/casper-bottom/22sslcert"):
            new_content = b"""#!/bin/sh
PREREQ=""
prereqs() { echo "$PREREQ"; }
case $1 in prereqs) prereqs; exit 0 ;; esac
exit 0
"""
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            offset = next_offset
            continue

        elif name == "usr/bin/casper-preseed":
            new_content = b"#!/bin/sh\nexit 0\n"
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            patched_preseed = True
            offset = next_offset
            continue

        elif name == "usr/bin/casper-set-selections":
            new_content = b"#!/bin/sh\nexit 0\n"
            new_filesize = len(new_content)
            new_file_pad_len = (4 - (new_filesize % 4)) % 4
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)
            new_cpio.extend(b'\x00' * new_file_pad_len)

            patched_selections = True
            offset = next_offset
            continue

        elif name == "conf/modules":
            # Empty out MD-RAID modules (linear, multipath, raid0-10) to avoid slow CPU benchmarking in VM
            new_content = b""
            new_filesize = 0
            new_file_pad_len = 0
            new_header = bytearray(header)
            new_header[54:62] = f"{new_filesize:08x}".encode('ascii')

            new_cpio.extend(new_header)
            new_cpio.extend(name_raw)
            new_cpio.extend(b'\x00' * name_pad_len)
            new_cpio.extend(new_content)

            patched_modules = True
            offset = next_offset
            continue

        # Keep original entry
        new_cpio.extend(decompressed[offset:next_offset])
        offset = next_offset

        if name == "TRAILER!!!":
            if offset < len(decompressed):
                new_cpio.extend(decompressed[offset:])
            break

    assert patched_casper, "Failed to patch scripts/casper"
    assert patched_functions, "Failed to patch scripts/casper-functions"
    assert patched_adduser, "Failed to patch scripts/casper-bottom/25adduser"
    assert patched_preseed, "Failed to patch usr/bin/casper-preseed"
    assert patched_selections, "Failed to patch usr/bin/casper-set-selections"
    print(f"Patched modules: {patched_modules}")

    pad_final = (512 - (len(new_cpio) % 512)) % 512
    new_cpio.extend(b'\x00' * pad_final)

    recompressed = pyzstd.compress(bytes(new_cpio), level_or_option=3)
    return prefix + recompressed

if __name__ == "__main__":
    initrd_path = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/initrd")
    new_data = patch_initrd_file(initrd_path)
    initrd_path.write_bytes(new_data)
    print(f"Successfully patched all components & wrote initrd! Size: {len(new_data)} bytes")
