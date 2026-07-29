#!/bin/bash
set -e

EXTRACT_DIR="$BUILD_DIR/iso_extracted"
SQUASHFS_DIR="$BUILD_DIR/squashfs-root"
OUTPUT_ISO="$BUILD_DIR/AppSuiteOS-amd64.iso"

echo "Rebuilding squashfs..."
if [ -f "$EXTRACT_DIR/casper/filesystem.squashfs" ]; then
    rm "$EXTRACT_DIR/casper/filesystem.squashfs"
    mksquashfs "$SQUASHFS_DIR" "$EXTRACT_DIR/casper/filesystem.squashfs" -comp xz
elif [ -f "$EXTRACT_DIR/install/filesystem.squashfs" ]; then
    rm "$EXTRACT_DIR/install/filesystem.squashfs"
    mksquashfs "$SQUASHFS_DIR" "$EXTRACT_DIR/install/filesystem.squashfs" -comp xz
fi

echo "Updating filesystem size..."
printf $(du -sx --block-size=1 "$SQUASHFS_DIR" | cut -f1) > "$EXTRACT_DIR/casper/filesystem.size" || true

echo "Generating ISO..."
cd "$EXTRACT_DIR"
grub-mkrescue -o "$OUTPUT_ISO" . \
    --volid "$ISO_LABEL" \
    --appid "AppSuite OS Built via Jarvis" \
    --publisher "Aachman Studios"

echo "Custom ISO successfully built: $OUTPUT_ISO"
