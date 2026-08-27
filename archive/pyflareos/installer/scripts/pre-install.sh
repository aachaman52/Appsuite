#!/usr/bin/env bash
# Calamares pre-install hook
set -euo pipefail
echo "[PyFlare Installer] Pre-install hook running..."
# Ensure PyFlare directories exist
mkdir -p /opt/pyflare/{bin,lib,engine,apps}
