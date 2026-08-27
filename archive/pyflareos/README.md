# PyFlare OS

<div align="center">
  <img src="branding/logos/svg/pyflare.svg" width="120" alt="PyFlare Logo">
  <h3>PyFlare OS — The AI-Native Linux Distribution</h3>
  <p>Ubuntu 24.04.2 LTS base · GNOME Desktop · Built for developers and AI systems</p>
</div>

---

## Overview

**PyFlare OS** is a custom Linux distribution based on Ubuntu 24.04.2 LTS. It provides a tightly integrated, AI-native operating system designed for the PyFlare ecosystem — featuring a custom desktop environment, purpose-built applications, and a procedurally generated visual identity system.

## Repository Structure

```
PyFlare/
├── branding/              Generated assets (logos, icons, wallpapers, themes, cursors)
├── branding_generator/    Python pipeline that generates all branding assets
├── config/                OS build configuration (packages, settings, GRUB)
├── filesystem/            Linux filesystem source tree (etc/, usr/, opt/)
├── desktop/               Desktop environment overrides (GNOME gsettings, dock, menus)
├── packages/              Package manifests, metadata, and dependency definitions
├── installer/             Calamares installer branding, config, and slides
├── applications/          Bundled application stubs (launchers, configs, assets)
├── validation/            Automated validators for all asset categories
├── scripts/               Build orchestration shell scripts
├── docs/                  Full documentation suite
└── tests/                 Automated test suite
```

## Quick Start

### Prerequisites
```bash
# Ubuntu/Debian Linux build environment
sudo apt update
sudo apt install -y squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools python3 python3-pip libcairo2-dev
pip install -r requirements.txt
```

### Generate Branding Assets
```bash
python -m branding_generator.main generate
python -m branding_generator.main validate
```

### Run Validators
```bash
python validation/run_all.py
```

### Build ISO (Linux only)
```bash
sudo python3 build.py --config config/default.yaml
```

## Documentation

| Document | Description |
|----------|-------------|
| [BUILD.md](docs/BUILD.md) | ISO build process and requirements |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Development workflow and tooling |
| [BRANDING.md](docs/BRANDING.md) | Visual identity system |
| [PACKAGING.md](docs/PACKAGING.md) | Package structure and manifests |
| [INSTALLER.md](docs/INSTALLER.md) | Calamares installer configuration |
| [DIRECTORY_STRUCTURE.md](docs/DIRECTORY_STRUCTURE.md) | Full tree reference |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | How to contribute |

## License

PyFlare OS is distributed under the [PyFlare Proprietary License](LICENSE).  
Component licenses (Ubuntu, GNOME, GTK, etc.) remain with their respective owners.
