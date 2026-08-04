# AppSuite Ecosystem — Installer

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

PyFlare OS ships with Calamares as its graphical installer. Calamares is the universal Linux system installer used by many distributions (KDE Neon, Manjaro, Garuda, etc.) and provides a modular, YAML-configured installation pipeline.

---

## Installer Location

```
PyFlare/installer/
├── README.md           Installer overview
├── config/             Calamares module YAML files
├── slides/             Installation slideshow (HTML/CSS/JS)
└── (branding assets deployed from branding/installer/)
```

---

## Calamares Configuration

Calamares modules are configured in `installer/config/`. Key modules:

| Module | Purpose |
|---|---|
| `welcome` | Welcome screen with language selection |
| `locale` | Timezone and locale selection |
| `keyboard` | Keyboard layout selection |
| `partition` | Disk partitioning (manual or automatic) |
| `users` | User account creation |
| `summary` | Installation summary confirmation |
| `install` | File copying, package installation |
| `bootloader` | GRUB installation and configuration |
| `finished` | Completion screen with restart option |

---

## Branding

Calamares reads product branding from configuration that references:

```
branding/installer/
├── logo.png            Sidebar product logo
└── background.png      Installer background image
```

Product strings (name, version, URLs) are sourced from `config/branding.yaml`.

---

## Installation Slideshow

`installer/slides/` contains an HTML/CSS/JS slideshow displayed during the file-copying phase:

| Slide | Content |
|---|---|
| 1 | PyFlare OS welcome — logo and tagline |
| 2 | Features — AI runtime, developer tools |
| 3 | Applications — overview of bundled apps |
| 4 | Community — links to support and documentation |

---

## Post-Installation

After file copy completes, `config/post_install.sh` runs in the new system to:

1. Set Plymouth theme: `update-alternatives --set default.plymouth pyflare`
2. Update initramfs: `update-initramfs -u`
3. Apply GRUB theme: copy theme files, update `/etc/default/grub`
4. Update GRUB: `update-grub`
5. Enable dconf system profile
6. Enable PyFlare systemd services
7. Set default GNOME theme and fonts via `gsettings`

---

## Network Installation

For network-connected installs, Calamares can:
- Install additional language packs
- Apply security updates from Ubuntu mirrors
- Install Snap and Flatpak packages from their respective stores

---

## Related Documents

| Document | Purpose |
|---|---|
| [BOOT_PROCESS.md](BOOT_PROCESS.md) | What happens after installation |
| [FILESYSTEM.md](FILESYSTEM.md) | Filesystem structure |
| [BRANDING.md](BRANDING.md) | Installer branding assets |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | How the installer is packaged |
