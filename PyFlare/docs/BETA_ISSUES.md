# PyFlare OS — Beta 1.0 Engineering Issue Catalog

This catalog tracks the highest-priority actionable engineering issues required to achieve Beta 1.0 release sign-off by 2 February 2027.

---

### ISSUE-01: Eliminate Plymouth Splash Screen Hang During Transition to GDM3
- **Priority:** **P0 — Blocker (Milestone Critical)**
- **Type:** Boot & Display Bug
- **Affected Subsystem:** Gate 1 (Boot & ISO), Gate 7 (Performance)
- **Relevant Files/Modules:**
  - `PyFlare/filesystem/etc/plymouth/plymouthd.conf`
  - `PyFlare/filesystem/etc/gdm3/custom.conf`
  - `PyFlare/scripts/fix_and_build_iso.py`
  - `PyFlare/scripts/patch_initrd.py`
- **Description:** On VirtualBox VMs, Plymouth splash screen can remain on the screen buffer while GDM3 starts behind it, requiring manual VT switching or explicit `plymouth quit` invocation. The system must automatically and cleanly dismiss Plymouth the instant GDM3 is ready to present the display.
- **Dependencies:** VMSVGA display controller, Xorg initialization.
- **Acceptance Criteria:**
  1. Boot from cold start in VirtualBox directly displays the GNOME Shell desktop without user pressing any keys.
  2. Total cold boot time from bootloader to interactive desktop is < 45 seconds.
  3. Plymouth daemon exits cleanly with return code 0 and releases DRM framebuffer.
- **Test Requirements:** Automated headless and GUI boot verification in VirtualBox 7.x; capture screenshot showing top bar, wallpaper, and dock.
- **Completion Evidence:** Saved screenshot showing GNOME desktop active and `systemctl status display-manager` returning active (running).

---

### ISSUE-02: Calamares Offline Installer End-to-End Disk Installation Validation
- **Priority:** **P1 — High (Release Gate 1 Requirement)**
- **Type:** Installation & Deployment
- **Affected Subsystem:** Gate 1 (Boot & ISO)
- **Relevant Files/Modules:**
  - `PyFlare/installer/config/settings.conf`
  - `PyFlare/installer/config/modules/*.conf`
  - `PyFlare/filesystem/usr/share/applications/io.calamares.calamares.desktop`
- **Description:** Verify that Calamares can perform an offline installation from the live ISO onto a fresh virtual hard disk (30 GB virtual SATA drive) with GPT/EFI partitioning and valid GRUB installation.
- **Dependencies:** Calamares binaries and squashfs unpack module.
- **Acceptance Criteria:**
  1. Calamares launches from the live desktop menu.
  2. Installation wizard completes partition formatting, rootfs copy, and bootloader installation without fatal errors.
  3. Rebooting the VM from disk (with ISO detached) boots successfully into the installed PyFlare OS.
- **Test Requirements:** Automated installation run on a secondary virtual disk in VirtualBox; verify GRUB EFI entry and `/etc/fstab` mounts.
- **Completion Evidence:** VirtualBox VM booted from SATA disk with `/dev/sda` mounted as `/`.

---

### ISSUE-03: PyFlare Control Plane Background Engine Daemon Lifecycle & CGroup Hardening
- **Priority:** **P1 — High (Release Gate 4 Requirement)**
- **Type:** Reliability & Resource Management
- **Affected Subsystem:** Gate 4 (Execution Engine), Gate 7 (Performance)
- **Relevant Files/Modules:**
  - `PyFlare/filesystem/etc/systemd/system/pyflare-engine.service`
  - `PyFlare/filesystem/opt/pyflare/engine/pyflare-engine`
  - `PyFlare/control_plane/src/pyflare_control/execution_engine.py`
- **Description:** Harden `pyflare-engine.service` with systemd cgroup v2 resource slices (`MemoryMax=1500M`, `CPUWeight=100`) so background AI tasks cannot starve foreground desktop responsiveness.
- **Dependencies:** systemd v255, Linux cgroup v2 unified hierarchy.
- **Acceptance Criteria:**
  1. `pyflare-engine.service` starts automatically in `multi-user.target` without failing.
  2. Exceeding memory limits triggers graceful worker preemption rather than kernel OOM panic.
  3. Foreground desktop frame rate remains steady during background execution.
- **Test Requirements:** Memory stress injection test via `pytest PyFlare/control_plane/tests/test_scheduler.py`.
- **Completion Evidence:** `systemctl status pyflare-engine.service` showing active (running) with MemoryCurrent bounded.

---

### ISSUE-04: PyFlare Application Suite Desktop Entry & GTK4 Window Initialization
- **Priority:** **P2 — Medium (Release Gate 6 Requirement)**
- **Type:** UI/UX & Desktop Integration
- **Affected Subsystem:** Gate 6 (Developer Environment)
- **Relevant Files/Modules:**
  - `PyFlare/applications/*/src/main.py`
  - `PyFlare/filesystem/usr/share/applications/dev.pyflare.*.desktop`
  - `PyFlare/filesystem/opt/pyflare/bin/pyflare-*`
- **Description:** Verify that all bundled PyFlare desktop applications (AI Assistant, Store, Package Manager, Settings, Terminal, Files) launch cleanly via their desktop entries and display responsive GTK4/Libadwaita windows.
- **Dependencies:** Python 3 PyGObject bindings, Libadwaita 1.5+.
- **Acceptance Criteria:**
  1. Clicking application icons in GNOME Dash launches corresponding process within 2.0s.
  2. Applications render with custom PyFlare-Dark theme and correct icon assets.
  3. No unhandled GTK or D-Bus exceptions in system journal.
- **Test Requirements:** Subprocess launch smoke test across all wrapper scripts in `/opt/pyflare/bin/`.
- **Completion Evidence:** Clean journal log with zero Gtk-CRITICAL warnings on application launch.

---

### ISSUE-05: Blender 4.x Python Worker Adapter & Asset Importer Integration
- **Priority:** **P2 — Medium (Release Gate 6 Requirement)**
- **Type:** Game Dev Pipeline
- **Affected Subsystem:** Gate 6 (Developer Environment)
- **Relevant Files/Modules:**
  - `PyFlare/control_plane/src/pyflare_control/router.py`
  - `PyFlare/control_plane/src/pyflare_control/registry.py`
  - `PyFlare/control_plane/src/pyflare_control/execution_engine.py`
- **Description:** Add the structured Blender headless execution adapter (`bpy`) to the capability registry (`blender.mesh.process`, `blender.gltf.export`) for automated 3D asset conversion in game development pipelines.
- **Dependencies:** Blender 4.0+ installation on target system.
- **Acceptance Criteria:**
  1. `blender.mesh.process` capability registered in `CapabilityRegistry`.
  2. Router directs 3D model processing tasks to local Blender worker.
  3. Converted GLTF/FBX models load cleanly into Unity 6 project folder.
- **Test Requirements:** Unit test in `PyFlare/control_plane/tests/test_router.py` verifying Blender capability routing.
- **Completion Evidence:** Unit test assertion demonstrating deterministic route to `blender-worker`.
