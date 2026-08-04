# AppSuite Ecosystem — Package System

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

PyFlare OS manages three categories of software packages: APT (system packages), Snap, and Flatpak. All are defined in `config/packages.yaml` — a single file that determines everything installed in the OS.

---

## Package Categories (APT)

| Category | Key Packages | Purpose |
|---|---|---|
| `base` | ubuntu-standard, linux-generic-hwe-24.04, grub-pc, grub-efi-amd64, systemd | Core OS |
| `desktop` | gnome-shell, gnome-session, gdm3, nautilus, gnome-terminal | Desktop environment |
| `graphics` | xorg, mesa-utils, libgl1-mesa-dri, vulkan-tools, nvidia-driver-535 | Display and GPU |
| `plymouth` | plymouth, plymouth-themes | Boot splash |
| `audio` | pipewire, pipewire-alsa, pipewire-pulse, wireplumber, pavucontrol | Audio routing |
| `networking` | network-manager, wireless-tools, openssh-client, nftables, ufw | Networking |
| `fonts` | fonts-noto, fonts-liberation, fonts-ubuntu, fontconfig | Typography |
| `printing` | cups, system-config-printer | Printing |
| `development` | git, python3, gcc, clang, gdb, cmake, docker.io | Developer tools |
| `containers` | docker.io, docker-compose, flatpak | Containers |
| `pyflare` | python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, libadwaita-1-dev | PyFlare Python bindings |
| `utilities` | vim, nano, timeshift, synaptic, gdebi | System utilities |

## Removed Packages (Debloat)

```yaml
remove:
  - thunderbird           # Replace with Firefox Snap
  - transmission-gtk      # Not needed by default
  - gnome-mahjongg        # Games removed
  - gnome-mines
  - gnome-sudoku
  - aisleriot
  - ubuntu-web-launchers  # Ubuntu branding launchers
  - apport                # Crash reporter
  - whoopsie              # Error reporting
```

## Snap Packages

```yaml
snaps:
  - name: firefox
    channel: stable
  - name: code
    channel: stable
    classic: true          # VS Code requires classic confinement
```

## Flatpak Applications

```yaml
flatpaks:
  - org.mozilla.firefox
  - com.visualstudio.code
  - org.gimp.GIMP
  - org.inkscape.Inkscape
  - io.github.flattool.Warehouse
```

## Custom Install Commands

```yaml
custom_installs:
  - description: "Install Ollama"
    command: "curl -fsSL https://ollama.com/install.sh | sh"
    condition: "network"

  - description: "Install PyFlare Python dependencies"
    command: "pip3 install Pillow cairosvg tqdm colorama numpy requests pyyaml imageio svglib reportlab"
    condition: "always"
```

---

## How Packages Are Installed

During the build, `scripts/setup_tree.py` reads `config/packages.yaml` and:

1. Enters the chroot rootfs environment
2. Runs `apt-get update`
3. Installs all packages by category using `apt-get install -y`
4. Removes debloat packages with `apt-get remove --purge`
5. Installs Snap packages via `snap install`
6. Installs Flatpak remote and apps
7. Runs custom install commands

GPU drivers (NVIDIA, AMD, Intel) are included but auto-detected at runtime — the wrong driver simply isn't loaded by the kernel.

---

## Validation

`validation/validate_packages.py` checks:
- All package names in `packages.yaml` are syntactically valid
- No duplicate entries across categories
- Remove list doesn't conflict with required packages

---

## Related Documents

| Document | Purpose |
|---|---|
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | How packages are installed during build |
| [FILESYSTEM.md](FILESYSTEM.md) | Where installed packages land |
| [INSTALLER.md](INSTALLER.md) | Calamares post-install configuration |
