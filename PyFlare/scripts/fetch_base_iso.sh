#!/bin/bash
set -e

ISO_NAME=$(basename "$BASE_ISO_URL")
ISO_PATH="$BUILD_DIR/$ISO_NAME"

if [ -f "$ISO_PATH" ]; then
    echo "Base ISO already exists at $ISO_PATH. Skipping download."
else
    echo "Downloading Base ISO..."
    wget -O "$ISO_PATH" "$BASE_ISO_URL"
fi
