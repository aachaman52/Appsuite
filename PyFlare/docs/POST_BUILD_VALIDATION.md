# PyFlare OS 1.0.0 Ember Beta - Engineering Validation Report

**Document Version:** 1.0.0  
**Validation Date:** 2026-11-01  
**Target Milestone:** 02 February 2027  
**Validation Engineer:** Senior Linux Distribution, QA & Release Engineer  

---

## 1. Build Information

| Property | Value |
|---|---|
| **Git Branch** | `perf/pyflare-virtualbox-low-memory` |
| **Commit Hash** | `16a1c0b` (HEAD) |
| **Previous Canonical Commit** | `b136098` |
| **ISO Filename** | `pyflare-os-1.0.0-ember-amd64.iso` |
| **Relative Path** | `PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso` |
| **ISO File Size** | 3,014,479,872 bytes (2,874.83 MB) |
| **SHA-256 Checksum** | `D5C823E4BA5EFFBD2792CE0939618FCEBCFC1A6D8532017A96561E308ACF049A` |
| **Base Distribution** | Ubuntu 24.04 LTS (Noble Numbat) |
| **Desktop Environment** | GNOME 46 (Xorg / GDM3 Autologin) |

---

## 2. VirtualBox Boot Results

### 2.1 VirtualBox VM Configuration (`Pyflare`)
The target hardware environment was inspected directly via `VBoxManage showvminfo Pyflare`:
- **Architecture:** x86_64
- **Allocated Memory (RAM):** 4096 MB (4.0 GB)
- **vCPU Cores:** 2 CPUs (Execution cap: 100%)
- **Firmware:** BIOS (Legacy mode, EFI disabled)
- **Graphics Controller:** VMSVGA
- **Video Memory (VRAM):** 128 MB
- **3D Acceleration:** Disabled
- **Boot Order:**
  1. DVD (Optical Drive)
  2. HardDisk (`sda`)
- **Storage Attachment:**
  - **IDE Controller (PIIX4) Port 0, Unit 0:** `PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso` (Bootable)
  - **SATA Controller (IntelAHCI) Port 0, Unit 0:** `Pyflare.vdi` (37.5 GB disposable disk)
- **UART / Serial Device:** UART 1 attached to `serial.log` (16550A)

### 2.2 Boot Progression and Timing
The VM was booted in headless mode and visual progression was captured via automated screenshot instrumentation:

| Milestone | Timestamp | Elapsed Time | Visual / Log State |
|---|---|---|---|
| **Boot Invocation** | 16:44:14.807 | 0.0s | GRUB menu initialization |
| **Initrd / Casper Stage** | 16:44:24.800 | 10.0s | Casper functions loaded, debconf non-blocking stub verified |
| **Systemd Multi-User** | 16:44:44.800 | 30.0s | `dbus.service`, `systemd-logind.service`, `accounts-daemon.service` started |
| **GDM Display Manager** | 16:44:57.000 | 42.2s | `gdm.service` started; `plymouth-quit-pyflare.service` finished cleanly |
| **Desktop Active** | 16:45:00.000 | 45.2s | GNOME Shell top panel rendered ("Sun Nov 1 11:15 AM", Activities pill, System tray) |

- **Time to Graphical Desktop:** **42.2 seconds** (well within target thresholds).
- **Plymouth Hang Status:** **RESOLVED**. No console lockup, spinlock, or indefinite splash screen hang.
- **Fail Whale Status:** **RESOLVED**. No crash dialog; dummy units and session guard overrides prevent premature session aborts.
- **Autologin Status:** **VERIFIED**. GDM3 automatically initiated the session for user `pyflare` (uid 1000).

### 2.3 System Runtime Metrics After Boot
Live telemetry collected from the operating system via `/dev/ttyS0` hardware serial pipe:
- **System Uptime & Load:** `11:23:34 up 9 min, 2 users, load average: 0.08, 0.28, 0.19`
- **Memory Consumption (`free -m`):**
  - Total: 3915 MB
  - Used: 693 MB (17.7% of total memory)
  - Free: 2392 MB
  - Shared: 165 MB
  - Buff/Cache: 1206 MB
  - Available: 3222 MB
  - Swap: 0 MB
- **GNOME Shell Processes:**
  - `gdm3` (PID 969)
  - `/usr/lib/xorg/Xorg vt1` (PID 2218, CPU 1.7%, MEM 1.8%)
  - `/usr/bin/gnome-shell` (PID 2257/3924, CPU 1.5%–4.0%, MEM 5.6%)
- **Failed Services:**
  - `pyflare-update.service`: Failed on initial boot due to network interface offline. Non-critical background task.
- **Kernel Log Warnings:**
  - `Failed to find module 'msr'`, `dm-multipath` (cosmetic hardware module load warnings).

---

## 3. Regression Test Results

The full regression test suite was executed against commit `16a1c0b`.

### 3.1 Control Plane Test Suite (`PyFlare/control_plane`)
**Command:** `python -m pytest tests/ -v`

| Component | Passed | Failed | Skipped | Status | Notes |
|---|---:|---:|---:|---|---|
| **Authentication** (`test_auth.py`) | 6 | 0 | 0 | PASSED | RBAC, tokens, permission boundaries |
| **CLI Dispatcher** (`test_cli.py`) | 6 | 0 | 0 | PASSED | CLI invocation, flags, task dispatch |
| **Codec Layer** (`test_codec.py`) | 4 | 0 | 0 | PASSED | Serialization, TaskSpec encoding |
| **Project Context Manager** (`test_context_manager.py`) | 6 | 0 | 0 | PASSED | SQLite project state, indexing |
| **Execution Engine** (`test_execution_engine.py`) | 7 | 0 | 0 | PASSED | Request execution, undo registry, rollback |
| **First-Boot Setup** (`test_firstboot.py`) | 4 | 0 | 0 | PASSED | Hardware profiling, configuration init |
| **Live Unity 6 Integration** (`test_live_unity_integration.py`) | 1 | 0 | 0 | PASSED (LIVE) | Executed against live Unity Editor 6000.0.69f1 in batchmode |
| **Model Registry** (`test_model_registry.py`) | 7 | 0 | 0 | PASSED | Hardware-aware model selection |
| **Performance Optimizations** (`test_performance_optimizations.py`) | 7 | 0 | 0 | PASSED | Latency scoring, low-memory routing |
| **Deterministic Router** (`test_router.py`) | 7 | 0 | 0 | PASSED | Deterministic capability matching |
| **Resource Scheduler** (`test_scheduler.py`) | 2 | 0 | 0 | PASSED | Budget limits, RAM/CPU allocation |
| **Security & Grants** (`test_security.py`) | 1 | 0 | 0 | PASSED | Cryptographic permission grants |
| **Unity Bridge Client** (`test_unity_client.py`) | 6 | 0 | 0 | PASSED | HTTP RPC protocol, retry logic |
| **Unity Package Contract** (`test_unity_package_contract.py`) | 3 | 0 | 0 | PASSED | Automation manifest & API conformance |
| **Unity Protocol Spec** (`test_unity_protocol.py`) | 2 | 0 | 0 | PASSED | Message framing & status enums |
| **Validation & Retry** (`test_validation_retry.py`) | 4 | 0 | 0 | PASSED | Self-healing schema validation retry |
| **Task Journal & Audit** (`test_workflow_journal.py`) | 5 | 0 | 0 | PASSED | SQLite TaskJournal & Redacted AuditLog |
| **Control Plane Subtotal** | **78** | **0** | **0** | **PASSED** | **Runtime: 82.10s** |

#### Live Unity 6 Integration Test Verification
- Executable located at: `C:/Program Files/Unity/Hub/Editor/6000.0.69f1/Editor/Unity.exe`
- Ran standalone via `python -m pytest tests/test_live_unity_integration.py -v -s`:
  - Result: **1 passed in 48.01s**.
  - Verified: Spawned Unity 6 Editor in batchmode with `com.aachmanstudios.pyflare.automation` package, established HTTP bridge, routed `game_object.create`, validated returned `GlobalObjectId`, verified `COMPLETED` state in SQLite TaskJournal, verified JSON Lines audit trail, and performed clean process termination.

### 3.2 Application Smoke Tests (`PyFlare/applications`)
**Command:** `python -m pytest PyFlare/applications --import-mode=importlib -v`

| Application Suite | Passed | Failed | Skipped | Status |
|---|---:|---:|---:|---|
| `ai-assistant` | 2 | 0 | 0 | PASSED |
| `appsuite` | 2 | 0 | 0 | PASSED |
| `browser` | 2 | 0 | 0 | PASSED |
| `engine` | 2 | 0 | 0 | PASSED |
| `files` | 2 | 0 | 0 | PASSED |
| `launcher` | 2 | 0 | 0 | PASSED |
| `package-manager` | 2 | 0 | 0 | PASSED |
| `plugin-manager` | 2 | 0 | 0 | PASSED |
| `settings` | 2 | 0 | 0 | PASSED |
| `store` | 2 | 0 | 0 | PASSED |
| `terminal` | 2 | 0 | 0 | PASSED |
| **Applications Subtotal** | **22** | **0** | **0** | **PASSED** |

### 3.3 Rootfs & Image Discovery Tests (`PyFlare/tests`)
**Command:** `python -m pytest PyFlare/tests/test_squashfs_discovery.py -v`

| Test Suite | Passed | Failed | Skipped | Status |
|---|---:|---:|---:|---|
| Squashfs Layer Discovery | 8 | 0 | 0 | PASSED |
| **Discovery Subtotal** | **8** | **0** | **0** | **PASSED** |

### 3.4 Grand Regression Total
- **Total Tests Executed:** **108**
- **Passed:** **108 (100%)**
- **Failed:** **0**
- **Skipped:** **0**
- **Not Executed:** **0**

---

## 4. Calamares Installation Results

| Item | Result |
|---|---|
| **Installation Status** | **BLOCKED / NOT EXECUTED** |
| **Storage Block Device Detection** | **PASSED** (`sda` 37.5 GB VirtualBox virtual disk detected by kernel) |
| **Calamares Binary in Live Rootfs** | **FAILED** (`which calamares` returned code 1; binary not found) |
| **Calamares Configuration in Rootfs** | **FAILED** (`/etc/calamares` does not exist in rootfs) |
| **Partitioning Execution** | **NOT EXECUTED** (Installer missing) |
| **Bootloader (GRUB) Installation** | **NOT EXECUTED** (Installer missing) |
| **EFI System Configuration** | **NOT EXECUTED** (Installer missing) |
| **Post-Installation Boot from Disk** | **NOT EXECUTED** (Installer missing) |

### 4.1 Root Cause Analysis for Calamares
Inspection of the ISO composition pipeline (`PyFlare/scripts/fix_and_build_iso.py`) revealed:
1. The base squashfs (`ubuntu-server-minimal.squashfs`) does not include the Debian/Ubuntu `calamares` package or `kpmcore`.
2. Although repository configurations exist under `PyFlare/installer/config/settings.conf` and `branding.desc`, `fix_and_build_iso.py` only merges `PyFlare/filesystem/`, `PyFlare/applications/`, and `PyFlare/control_plane/`. It never copies `PyFlare/installer/config/` into `/etc/calamares/`.
3. In the live VM session, `enp0s3` is down by default, preventing on-demand `apt install calamares`.

---

## 5. Remaining Issues

### ISSUE-CALAMARES-01: Calamares Package & Configuration Omission from ISO Build
- **Severity:** High (Release Blocker for Beta 1.0)
- **Root Cause:** Build script `fix_and_build_iso.py` does not stage `calamares` binaries into base squashfs or copy `installer/config` into `/etc/calamares`.
- **Reproduction Steps:**
  1. Boot `pyflare-os-1.0.0-ember-amd64.iso` in VirtualBox.
  2. Execute `which calamares` or `ls -d /etc/calamares`.
  3. Observe exit status 1 / no file found.
- **Proposed Fix:**
  1. Add `calamares` package staging step (or bundle offline debs) to rootfs during ISO generation.
  2. Add `shutil.copytree(pyflare_root / "installer" / "config", overlay_dir / "etc" / "calamares")` in `fix_and_build_iso.py`.
  3. Place desktop entry launcher at `/usr/share/applications/io.calamares.calamares.desktop`.
- **Current Status:** Documented as release blocker.

### ISSUE-NET-01: Default Ethernet Interface Down on Live Boot
- **Severity:** Low
- **Root Cause:** In minimal server base, `enp0s3` has no active DHCP netplan rule in `/etc/netplan/` on live boot.
- **Reproduction Steps:** Run `ip a` on live boot; observe `enp0s3: state DOWN`.
- **Proposed Fix:** Include `/etc/netplan/01-netcfg.yaml` with `dhcp4: true` for all ethernet interfaces in the overlay.
- **Current Status:** Documented.

---

## 6. Release Readiness Evaluation

### Decision: **AMBER** (Some critical gates remain unverified)

**Justification:**
1. **Gate 1 (Live Boot & Desktop):** **GREEN**. The ISO boots reliably in VirtualBox under minimum target hardware (4 GB RAM, 2 vCPU). Boot time is ~42 seconds. Plymouth splash freeze and fail-whale crashes are completely resolved. RAM usage is exceptionally lean (693 MB).
2. **Gate 2 (Regression & Control Plane):** **GREEN**. All 108 automated unit and integration tests passed with 0 failures. The live Unity 6000.0.69f1 batchmode vertical slice is thoroughly verified against a real editor process.
3. **Gate 3 (Calamares End-to-End Installation):** **AMBER / RED BLOCKED**. The installer binary was omitted from the rootfs squashfs layers during ISO assembly. As a result, end-to-end installation to virtual disk (`sda`) could not be verified.

Per the engineering release criteria:
- **GREEN** is forbidden because the installer gate remains unverified.
- **AMBER** accurately reflects that core OS boot, performance, control plane, and live Unity vertical slice are verified, while installation packaging must be completed for final release sign-off.
