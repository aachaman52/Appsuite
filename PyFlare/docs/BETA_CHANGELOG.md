# PyFlare OS — Beta 1.0 Changelog

All notable changes to the PyFlare operating system and control plane will be documented in this file.

---

## [1.0.0-beta] — 2026-11-01 (Current Milestone)

### Added
- **Authenticated Unity 6 Editor Bridge:** Loopback HTTP RPC bridge (`com.aachmanstudios.pyflare.automation`) supporting authenticated batchmode and GUI command execution with Unity Undo integration.
- **Project Context Manager:** SQLite-backed versioned file indexer with semantic search, symbol extraction, and automated secret exclusion (`ProjectContextManager`).
- **Dynamic ZRAM Swap:** `pyflare-zram.service` allocating 50% physical RAM as zstd-compressed swap, preventing out-of-memory lockups on 4 GB RAM VMs.
- **Hardware-Aware Model Tier Registry:** Dynamic categorization of host capabilities (`detect_hardware`), automatically assigning conservative `API_ONLY` or minimal local tiers on constrained systems.
- **Remaster & Build Pipeline:** Streamlined 90-second ISO remaster script (`fix_and_build_iso.py`) leveraging cached pristine initrd and Casper overlay filesystem layers.
- **Formal Release Management Artifacts:** `BETA_ROADMAP.md`, `BETA_STATUS.md`, `BETA_ACCEPTANCE_CRITERIA.md`, `BETA_TEST_MATRIX.md`, `BETA_RELEASE_CHECKLIST.md`, and `BETA_ISSUES.md`.

### Fixed
- **Casper Debconf FIFO Spinlock:** Patched `scripts/casper-functions:load_confmodule()` in initrd to replace uninitialized fd 4 reads with non-blocking dummy stubs, eliminating the 30-minute boot lockup and CPU watchdog crash.
- **VirtualBox Graphics Freezes:** Switched display adapter from legacy `vboxsvga` to standard `vmsvga` with 128 MB VRAM and 3D acceleration; forced GDM3 to Xorg session (`WaylandEnable=false`).
- **Systemd Service Ordering Cycles:** Resolved circular dependency between `pyflare-zram.service` and `local-fs.target`.
- **GNOME Shell Theme Widget Missing Base:** Injected `@import url("resource:///org/gnome/shell/theme/gnome-shell.css");` into PyFlare-Dark theme and fixed fallback cursor symlink to `Adwaita`.
- **Casper Overlay User Permissions:** Enforced correct root ownership on system directories and `1000:1000` ownership on `/home/pyflare`.

### Changed
- **ISO Boot Loader Defaults:** Removed obsolete `nomodeset` kernel flag from default GRUB menu entry, reserving it for the Safe Graphics recovery entry.
- **Automated Login:** Pre-configured GDM3 `custom.conf` for instant autologin of the `pyflare` developer account into GNOME on Xorg.

---

## [1.0.0-alpha.2] — 2026-10-02
- Merged deterministic control plane foundation with task journal and audit log sinks.
- Added TaskSpec JSON Schema validator and codec.
- Integrated initial Calamares installer configuration.

## [1.0.0-alpha.1] — 2026-08-04
- Initial remastered Ubuntu 24.04 LTS live server base image.
- Custom PyFlare branding assets (wallpapers, plymouth theme, icons, GTK theme).
