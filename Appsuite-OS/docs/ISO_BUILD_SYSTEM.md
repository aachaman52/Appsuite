# AppSuite OS ISO Build System

## Build Flow
AppSuite OS uses an automated Python-based pipeline to remaster the official Ubuntu 24.04 LTS ISO. The pipeline leverages the underlying principles of Cubic but abstracts them into a CI/CD-friendly, zero-interaction script.

The complete workflow executes as follows:
1. **Dependency Verification** (`verify_dependencies.py`): Ensures Python, Git, xorriso, squashfs-tools, and rsync are installed on the host system.
2. **Download & Checksum** (`download_base.py`): Idempotently fetches the Ubuntu 24.04 ISO from canonical servers and verifies its SHA256 integrity.
3. **Extraction** (`build_iso.py`): Mounts the ISO, copies its contents via `rsync`, and unpacks the root filesystem into `build/squashfs-root`.
    * **SquashFS Discovery**: Dynamically searches `casper/` and `install/` for `*.squashfs` files. It prioritizes `ubuntu-server-minimal.squashfs` (used in recent Ubuntu 24.04 server releases) over `filesystem.squashfs`, and strictly ignores any files containing `installer` in the name.
4. **Chroot Customization** *(Phase 3)*: `chroot` into the unpacked filesystem to install AppSuite dependencies (Godot, Blender, FFmpeg) using configuration from `config/default.yaml`.
5. **Repacking** *(Upcoming Phase)*: Compresses the modified filesystem back into `filesystem.squashfs` and generates the final bootable ISO using `grub-mkrescue` and `xorriso`.

## Directory Structure
```
Appsuite-OS/
├── build/                 # Ephemeral working directory for ISO extraction
├── config/                # YAML configuration files for the OS
│   └── default.yaml       # Core ISO properties (Hostname, Desktop Environment, Version)
├── docs/                  # Documentation
│   └── ISO_BUILD_SYSTEM.md
├── logs/                  # Structured execution logs
│   ├── build.log
│   └── errors.log
└── scripts/               # Core Python build pipeline
    ├── build_iso.py       # Main orchestrator script
    ├── clean.py           # Cleans the build directory
    ├── download_base.py   # Fetches and verifies the base ISO
    └── verify_dependencies.py
```

## Required Tools
This pipeline requires a Debian/Ubuntu host environment with root privileges and the following packages:
* `python3` and `python3-yaml`
* `squashfs-tools` (for `unsquashfs` and `mksquashfs`)
* `xorriso` (for ISO creation)
* `rsync` (for reliable filesystem copying)

## How to build an ISO
1. Clone this repository onto a Linux machine (or WSL2).
2. Install the python dependencies: `pip install pyyaml`.
3. Run the primary orchestrator:
   ```bash
   sudo python3 scripts/build_iso.py
   ```

## How to customize the ISO
To change the output ISO name, version, or desktop environment, edit `config/default.yaml`.
For package customization and visual branding, the `squashfs-root` folder will be injected with themes during the chroot step of the pipeline (to be fully implemented in the next phase).

---

*Note: We chose a custom Python CLI automation over Cubic (which is GUI-only) to guarantee CI/CD compatibility. We also opted to remaster the official Ubuntu Server ISO rather than using `live-build` from scratch, as it guarantees perfect feature parity with canonical releases and hardware drivers (like NVIDIA HWE).*
