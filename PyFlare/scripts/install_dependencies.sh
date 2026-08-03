#!/usr/bin/env bash
# PyFlare OS — Native Linux Dependency Installer
# Automatically installs all required tools to build the PyFlare OS ISO.

set -euo pipefail

echo "==========================================================="
echo "   PyFlare OS — Build Dependency Installer                 "
echo "==========================================================="

if [ "$EUID" -ne 0 ]; then
  echo "[FATAL] Please run as root (sudo ./install_dependencies.sh)"
  exit 1
fi

echo "[INFO] Checking OS..."
if ! grep -q "Ubuntu" /etc/os-release; then
  echo "[WARNING] This script is optimized for Ubuntu 24.04 LTS. Proceed with caution."
fi

echo "[INFO] Updating APT repositories..."
apt-get update -q

echo "[INFO] Installing core ISO and SquashFS build tools..."
DEPS=(
    "squashfs-tools"
    "xorriso"
    "grub-pc-bin"
    "grub-efi-amd64-bin"
    "mtools"
    "dosfstools"
    "python3"
    "python3-pip"
    "python3-yaml"
    "qemu-system-x86"
    "ovmf"
    "glib-compile-schemas"
)

apt-get install -y --no-install-recommends "${DEPS[@]}"

echo "[INFO] Verifying critical tools..."
MISSING=0
for tool in mksquashfs xorriso grub-mkrescue qemu-system-x86_64 glib-compile-schemas; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "[ERROR] Missing tool: $tool"
        MISSING=$((MISSING + 1))
    fi
done

if [ "$MISSING" -gt 0 ]; then
    echo "[FATAL] Dependency installation failed. $MISSING tools are missing."
    exit 1
fi

echo "==========================================================="
echo "[SUCCESS] All build dependencies installed."
echo "[SUCCESS] The host is ready for 'python3 build.py'."
echo "==========================================================="
