#!/usr/bin/env bash
# Calamares post-install hook — runs inside installed system chroot
set -euo pipefail
TARGET="${{1:-/}}"
echo "[PyFlare Installer] Post-install hook for target: $TARGET"

# Enable services
chroot "$TARGET" systemctl enable pyflare-engine.service 2>/dev/null || true
chroot "$TARGET" systemctl enable gdm3.service 2>/dev/null || true
chroot "$TARGET" glib-compile-schemas /usr/share/glib-2.0/schemas/ 2>/dev/null || true
chroot "$TARGET" fc-cache -f 2>/dev/null || true
chroot "$TARGET" update-initramfs -u 2>/dev/null || true
chroot "$TARGET" update-grub 2>/dev/null || true

echo "[PyFlare Installer] Post-install complete."
