#!/bin/bash
set -e

ISO_NAME=$(basename "$BASE_ISO_URL")
ISO_PATH="$BUILD_DIR/$ISO_NAME"
EXTRACT_DIR="$BUILD_DIR/iso_extracted"
SQUASHFS_DIR="$BUILD_DIR/squashfs-root"

echo "Extracting ISO contents..."
rm -rf "$EXTRACT_DIR" "$SQUASHFS_DIR"
mkdir -p "$EXTRACT_DIR"

# Mount and extract the ISO
MNT_DIR=$(mktemp -d)
mount -o loop "$ISO_PATH" "$MNT_DIR"
cp -rT "$MNT_DIR" "$EXTRACT_DIR"
umount "$MNT_DIR"
rm -rf "$MNT_DIR"

echo "Unsquashing filesystem..."
if [ -f "$EXTRACT_DIR/casper/filesystem.squashfs" ]; then
    unsquashfs -d "$SQUASHFS_DIR" "$EXTRACT_DIR/casper/filesystem.squashfs"
elif [ -f "$EXTRACT_DIR/install/filesystem.squashfs" ]; then
    unsquashfs -d "$SQUASHFS_DIR" "$EXTRACT_DIR/install/filesystem.squashfs"
else
    echo "Could not find filesystem.squashfs!"
    exit 1
fi
