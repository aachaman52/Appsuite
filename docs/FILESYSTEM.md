# AppSuite Ecosystem — Filesystem Overlay

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

The `PyFlare/filesystem/` directory is a partial Linux root filesystem tree. During the build, its contents are copied (overlaid) on top of the Ubuntu base rootfs, adding and replacing files to customise the system.

This approach avoids modifying the Ubuntu base — all PyFlare customisations live in this overlay and are fully versionable.

---

## Directory Map

```
filesystem/
├── boot/
│   ├── grub/
│   │   ├── themes/pyflare/     GRUB theme (background, font, colours)
│   │   └── grub.cfg            Custom GRUB menu configuration
│   └── plymouth/
│       └── themes/pyflare/     Plymouth boot splash theme
│
├── etc/
│   ├── dconf/
│   │   ├── db/local.d/
│   │   │   └── 00-pyflare      GNOME default settings (gsettings overrides)
│   │   └── profile/
│   │       └── user            dconf user profile pointing to local.d
│   ├── gdm3/
│   │   └── custom.conf         GDM3 display manager configuration
│   ├── systemd/
│   │   └── system/
│   │       ├── pyflare-engine.service   PyFlare Engine systemd unit
│   │       └── ollama.service           Ollama AI runtime unit
│   ├── os-release              PyFlare OS identification strings
│   ├── lsb-release             LSB compatibility identification
│   ├── hostname                Default hostname: pyflare
│   ├── hosts                   Local hostname resolution
│   └── xdg/
│       └── menus/
│           └── pyflare.menu    XDG application menu definition
│
├── home/
│   └── pyflare/                Default user skeleton
│       └── .config/
│           └── gtk-4.0/        GTK4 user settings
│
├── opt/
│   └── pyflare/                PyFlare application bundles
│       ├── engine/             PyFlare Engine service
│       └── apps/               Application data directories
│
├── root/                       Root user configuration
│   └── .bashrc                 Custom prompt and PATH
│
└── usr/
    ├── share/
    │   ├── applications/       .desktop launcher files (11 apps)
    │   ├── backgrounds/
    │   │   └── pyflare/        Wallpapers (deployed from branding/)
    │   ├── icons/
    │   │   └── PyFlare-Icons/  Icon theme (deployed from branding/)
    │   ├── plymouth/
    │   │   └── themes/pyflare/ Boot splash (deployed from branding/)
    │   ├── themes/
    │   │   └── PyFlare-Dark/   GTK theme (deployed from branding/)
    │   ├── fonts/
    │   │   └── pyflare/        Brand fonts (Inter, Space Grotesk, JetBrains Mono)
    │   └── gnome-shell/
    │       └── theme/pyflare/  GNOME Shell CSS theme
    └── bin/
        └── pyflare             PyFlare CLI entry point
```

---

## Key Files

### `/etc/os-release`

Identifies the OS to system tools:

```ini
PRETTY_NAME="PyFlare OS 1.0.0 (Ember)"
NAME="PyFlare OS"
VERSION="1.0.0 (Ember)"
ID=pyflare
ID_LIKE=ubuntu
VERSION_CODENAME=ember
HOME_URL="https://pyflare.dev"
SUPPORT_URL="https://aachmanstudios.dev/support"
BUG_REPORT_URL="https://github.com/aachman-studios/pyflare-os/issues"
```

### `/etc/dconf/db/local.d/00-pyflare`

GNOME default settings applied to all users:

```ini
[org/gnome/desktop/interface]
gtk-theme='PyFlare-Dark'
icon-theme='PyFlare-Icons'
cursor-theme='PyFlare-Cursors'
font-name='Inter 11'
document-font-name='Inter 11'
monospace-font-name='JetBrains Mono 11'
color-scheme='prefer-dark'

[org/gnome/desktop/background]
picture-uri='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
picture-uri-dark='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
```

### `/etc/systemd/system/pyflare-engine.service`

```ini
[Unit]
Description=PyFlare Engine
After=graphical.target network.target
Wants=ollama.service

[Service]
Type=simple
User=pyflare
ExecStart=/opt/pyflare/engine/pyflare-engine
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=graphical.target
```

---

## Overlay Injection Process

During build, `scripts/setup_tree.py` walks the `filesystem/` tree and copies each file into the corresponding path in `build/rootfs/`:

```python
for src in filesystem_dir.rglob("*"):
    if src.is_file():
        dst = rootfs_dir / src.relative_to(filesystem_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
```

File permissions defined in `validation/validate_permissions.py` are enforced after injection.

---

## Desktop Configuration

In addition to `filesystem/etc/dconf/`, the `desktop/` directory provides GNOME-specific configuration:

| Path | Content |
|---|---|
| `desktop/gsettings/` | Additional gsettings dump files |
| `desktop/dock/` | Dash-to-Dock JSON config |
| `desktop/menus/` | XDG menu XML definitions |
| `desktop/autostart/` | XDG autostart .desktop files |
| `desktop/shortcuts/` | Custom keyboard shortcut definitions |

---

## Validation

`validation/validate_filesystem.py` checks that all required paths exist in the overlay before the build proceeds.

---

## Related Documents

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [BOOT_PROCESS.md](BOOT_PROCESS.md) | How the filesystem is used at boot |
| [BRANDING.md](BRANDING.md) | How branding assets land in the filesystem |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | How the overlay is injected |
