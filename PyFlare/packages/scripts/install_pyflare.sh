#!/usr/bin/env bash
# PyFlare OS package installer — runs inside chroot
set -euo pipefail
PYFLARE_ROOT=/opt/pyflare

echo "Installing PyFlare OS packages..."
install -d "$PYFLARE_ROOT"/{bin,lib,engine,apps,plugins,themes,share}

# Copy filesystem overlay
rsync -av --no-owner --no-group \
    /tmp/pyflare-overlay/filesystem/ / \
    --exclude='.keep' \
    --exclude='README.md'

# Set permissions
chmod +x "$PYFLARE_ROOT"/bin/*
chmod +x "$PYFLARE_ROOT"/engine/pyflare-engine

# Enable services
systemctl enable pyflare-engine.service || true
systemctl enable pyflare-update.timer   || true
systemctl enable pyflare-firstrun.service || true

# Compile gsettings schemas
glib-compile-schemas /usr/share/glib-2.0/schemas/ || true

echo "PyFlare OS packages installed."
