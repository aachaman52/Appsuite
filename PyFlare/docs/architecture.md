# PyFlare OS Architecture

## System Stack

```
┌─────────────────────────────────────┐
│           User Applications         │
│  Terminal  Browser  Files  Store ... │
├─────────────────────────────────────┤
│          PyFlare Engine              │
│  AI Runtime · Plugin Manager        │
│  Package Backend · Event Bus        │
├─────────────────────────────────────┤
│         GNOME Desktop                │
│  GNOME Shell · GDM3 · Wayland/X11   │
├─────────────────────────────────────┤
│        Ubuntu 24.04 LTS Base         │
│  APT · systemd · D-Bus · udev       │
├─────────────────────────────────────┤
│      Linux Kernel (HWE 24.04)       │
└─────────────────────────────────────┘
```

## PyFlare Engine

D-Bus service (`dev.pyflare.Engine`) that provides:
- AI inference via Ollama (local LLM)
- Plugin management
- Package metadata aggregation
- System event bus

## Application Model

All bundled apps are Python + GTK4/libadwaita applications.
They communicate with PyFlare Engine via D-Bus.

## Build System

```
build.py
 ├── download_base.py     Fetch Ubuntu ISO
 ├── prepare_rootfs.py    Build filesystem overlay
 ├── copy_branding.py     Deploy branding assets
 ├── package_apps.py      Install app stubs
 ├── chroot_manager.py    Manage chroot environment
 └── package_iso.py       Assemble final ISO
```
