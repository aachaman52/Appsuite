# The Build Process

The `build.py` script orchestrates a 4-step execution pipeline to master the ISO:

1. **`fetch_base_iso.sh`**: Downloads the minimal Ubuntu base ISO if not cached in `build/`.
2. **`extract_iso.sh`**: Mounts the ISO to a loop device, copies the `casper` structure, and calls `unsquashfs` to decompress the core Linux filesystem into `squashfs-root`.
3. **`chroot_env.sh`**: Binds the host machine's `sys` and `proc` pseudo-filesystems into the `squashfs-root`, injects network resolution, then executes a `chroot`. Inside the chroot, `apt-get install` installs dependencies listed in `config/packages.yaml`, and `post_install.sh` executes for user creation.
4. **`generate_iso.sh`**: Repacks the customized `squashfs-root` using `mksquashfs -comp xz`, recalculates sizes, and packages the bootable binary via `grub-mkrescue`.
