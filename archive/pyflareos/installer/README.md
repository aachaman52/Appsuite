# PyFlare OS Installer (Calamares)

## Overview

PyFlare OS uses [Calamares](https://calamares.io/) as its graphical installer.

## Structure

| Path | Purpose |
|------|---------|
| `config/settings.conf` | Main Calamares configuration |
| `config/branding.desc` | Branding strings and images |
| `slides/` | HTML/QML installation slideshow |
| `scripts/pre-install.sh` | Pre-install hook |
| `scripts/post-install.sh` | Post-install hook |

## Building

Calamares runs from the live ISO session. The config files are copied to
`/etc/calamares/` during ISO build.

## Required Images

Place these in `installer/config/`:
- `pyflare-logo.png` — 200×200 installer logo
- `pyflare-icon.png` — 64×64 application icon
- `pyflare-welcome.png` — 540×240 welcome banner
- `pyflare-banner.png` — 800×420 sidebar banner
