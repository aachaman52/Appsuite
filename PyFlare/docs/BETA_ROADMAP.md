# PyFlare OS — Beta 1.0 Execution Roadmap

**Target Beta Release:** 2 February 2027  
**Planning Date:** 1 November 2026  
**Primary Target:** PyFlare for Game Developers (Ubuntu 24.04 LTS / GNOME 46 / Unity 6 Integration)  
**Authoritative Development Branch:** `perf/pyflare-virtualbox-low-memory`  

---

## 1. Executive Summary & Timeline Overview

| Phase | Timeframe | Focus Area | Key Deliverables & Gates | Milestone Impact |
|---|---|---|---|---|
| **Phase 1** | **1–14 Nov 2026** | **Foundation Audit & Alignment** | Canonical source established, branch divergence audited, circular dependencies resolved, test baseline certified (78/78 tests verified). | Baseline Established |
| **Phase 2** | **15–28 Nov 2026** | **Performance & ISO Reliability** | VirtualBox low-memory hardening (4 GB RAM, 2 vCPUs), casper debconf lockup resolution, dynamic zram, sub-30s boot target. | Live ISO Validated |
| **Phase 3** | **29 Nov–13 Dec 2026** | **Core System Completion** | Full control plane integration, context manager streaming, deterministic router v1, credential vault isolation. | System Workflows Complete |
| **Phase 4** | **14–27 Dec 2026** | **System Integration & Unity 6** | Real Unity 6 Editor batchmode & GUI automation bridge, Blender pipeline hooks, offline fallback enforcement. | Vertical Slice Integrated |
| **Phase 5** | **28 Dec–10 Jan 2027** | **Feature Freeze & Security Hardening** | Zero new features, least-privilege PAM/sudoers enforcement, Calamares installer verification, memory leak audit. | Beta Release Candidate 1 |
| **Phase 6** | **11–24 Jan 2027** | **Release Validation & Regression** | Clean VM matrix testing (VirtualBox, QEMU, bare-metal), recovery benchmarks, automated regression suite. | Beta Release Candidate 2 |
| **Phase 7** | **25 Jan–2 Feb 2027** | **Final Release Delivery** | Final ISO assembly (`pyflare-os-1.0.0-beta-amd64.iso`), SHA-256 validation, release notes, signed release tag `v1.0.0-beta`. | **Beta 1.0 Release** |

---

## 2. Phase-by-Phase Detailed Objectives & Deliverables

### Phase 1: Foundation Audit (1–14 November 2026)
- **Objective:** Reconcile branch histories (`main`, `feat/pyflare-beta-execution`, `perf/pyflare-virtualbox-low-memory`, `refactor/pyflare-cleanup`).
- **Dependencies:** Complete repository inspection, Python 3.12/3.15 test verification.
- **Deliverables:**
  - `BETA_STATUS.md` and `BETA_ROADMAP.md` published to repository.
  - Elimination of circular dependencies in `pyflare-zram.service` and `pyflare-engine.service`.
  - Fix permission race conditions in Casper initrd user setup.
  - 100% pass rate maintained across `PyFlare/control_plane/tests`.

### Phase 2: Performance and ISO (15–28 November 2026)
- **Objective:** Deliver a responsive, bootable PyFlare ISO that boots in < 30 seconds on a 4 GB RAM, 2 vCPU VirtualBox VM.
- **Dependencies:** Casper initrd non-blocking FIFO patch, VMSVGA display controller support.
- **Deliverables:**
  - Automated fast ISO remaster pipeline (`PyFlare/scripts/fix_and_build_iso.py`) completing under 120 seconds.
  - GDM3 auto-login with Wayland disabled for hypervisor compatibility.
  - ZRAM memory compression active and consuming < 50% physical RAM.
  - Verification screenshots captured via `VBoxManage controlvm screenshotpng`.

### Phase 3: Core System Completion (29 November–13 December 2026)
- **Objective:** Finalize control plane execution engine, project context manager, and deterministic routing.
- **Dependencies:** SQLite journal, audit log JSON Lines sink, hardware snapshot profiler.
- **Deliverables:**
  - `TaskSpec` validation and schema enforcement.
  - Offline capability guarantees (cloud providers filtered when disconnected).
  - Secret redaction across all audit trails and standard error streams.
  - First-boot interactive setup engine (`pyflare-firstrun`).

### Phase 4: System Integration (14–27 December 2026)
- **Objective:** Complete end-to-end integration between PyFlare control plane and Unity 6 Editor.
- **Dependencies:** `com.aachmanstudios.pyflare.automation` package, Unity 6000.0.69f1+.
- **Deliverables:**
  - Real vertical slice execution: `game_object.create`, `scene.modify`, `asset.import`.
  - Undo/redo safety stack in Unity Editor bridge.
  - Bounded task permission enforcement (`Permission.READ`, `Permission.WRITE`, `Permission.EXECUTE`).
  - Desktop launcher entries and GNOME dock integration.

### Phase 5: Feature Freeze & Hardening (28 December 2026–10 January 2027)
- **Objective:** Code freeze, defect reduction, and security tightening.
- **Dependencies:** All Phase 1–4 features merged into authoritative branch.
- **Deliverables:**
  - Strict file permissions on `/etc/sudoers.d` (0440) and `/home/pyflare` (0750).
  - Removal of experimental and unverified debug scripts.
  - Calamares offline installer module validation.
  - Generation of Release Candidate 1 (`RC1`).

### Phase 6: Release Validation (11–24 January 2027)
- **Objective:** Clean validation across target hypervisors and hardware targets.
- **Dependencies:** RC1 ISO artifact, Oracle VirtualBox 7.x, QEMU/KVM.
- **Deliverables:**
  - Clean VM boot benchmarks: total boot time, idle memory, swap usage, CPU load.
  - Recovery and rollback testing under failed tasks.
  - Generation of Release Candidate 2 (`RC2`).

### Phase 7: Release (25 January–2 February 2027)
- **Objective:** Production sign-off and public distribution.
- **Dependencies:** Zero open release blockers, passing acceptance test matrix.
- **Deliverables:**
  - Final ISO: `pyflare-os-1.0.0-beta-amd64.iso`.
  - SHA256 checksums and GPG signatures.
  - Release announcement, install guide, and user manual.
  - Git tag `v1.0.0-beta`.
