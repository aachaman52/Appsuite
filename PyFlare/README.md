# AppSuite OS

AppSuite OS is a custom Linux distribution based on **Ubuntu 24.04 LTS**. It is designed to act as the native environment for AppSuite autonomous engineering systems, providing a tightly integrated, highly optimized, and aesthetically pleasing operating system for AI-assisted software development.

## Project Structure

* **`build/`**: Working directory for ISO generation (not tracked in Git).
* **`config/`**: Configuration files for the OS, including preinstalled packages and system settings.
* **`branding/`**: Custom themes, wallpapers, icons, and boot splash screens.
* **`docs/`**: Comprehensive documentation on architecture and customization.
* **`scripts/`**: Core shell scripts that drive the ISO build process.
* **`build.py`**: The primary Python orchestrator script to build the OS.

## Getting Started

Building a custom ISO requires a Linux environment (or WSL2) with `root` privileges.

### Requirements

```bash
sudo apt update
sudo apt install -y squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools python3 python3-pip
pip install -r requirements.txt
```

### Build the ISO

Run the build orchestrator (must be run as root to handle chroot environments):

```bash
sudo python3 build.py
```

## Architecture

This project does **not** create a new Linux kernel or custom package manager. It leverages standard Debian/Ubuntu build paradigms (chroot, unsquashfs, mksquashfs) to remaster the official Ubuntu 24.04 LTS minimal ISO into a fully customized AppSuite OS.

For more information, see the [Documentation](docs/).
