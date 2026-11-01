# PyFlare OS — Beta 1.0 Release Checklist

**Release Milestone:** Beta 1.0 (`v1.0.0-beta`)  
**Target Date:** 2 February 2027  
**Gatekeeper:** Technical Lead & Systems Architect  

---

## 1. Gate Sign-Off Matrix

Every item must be marked `[X] PASSED` prior to generating the final release candidate.

### Gate 1: Bootable & Installable OS
- [x] Hybrid ISO boots in BIOS and UEFI environments without kernel panic.
- [x] Casper initrd patches eliminate `debconf-communicate` spinlocks and watchdog timeouts.
- [x] GDM3 display manager launches and auto-logins to GNOME 46 session on Xorg.
- [ ] Calamares offline installer successfully installs OS to a clean virtual hard disk.
- [ ] Installed system reboots cleanly from local disk without ISO media attached.

### Gate 2: Hardware-Aware Intelligence
- [x] Hardware detection accurately queries CPU, memory, GPU, and VRAM.
- [x] Model tier recommendations conservatively fallback to `API_ONLY` on low-resource machines.
- [x] Storage space check prevents downloading large weights on constrained disks.
- [x] Hardware profiling caching reduces repeat latency to < 10 ms.

### Gate 3: Control Plane & Task Routing
- [x] `TaskSpec` codec enforces strict typing and rejects unmapped fields.
- [x] Deterministic router produces 100% reproducible provider routes for given inputs.
- [x] Local tools take precedence over generative cloud models for deterministic operations.
- [x] Disconnected / offline states cleanly filter cloud model providers.

### Gate 4: Execution Engine & Audit Trail
- [x] End-to-end task lifecycle state transitions persist in SQLite journal.
- [x] Idempotency checks return cached results for duplicate task IDs.
- [x] Append-only audit log records requests, grants, routes, and responses.
- [x] Process timeouts cleanly terminate unresponsive child executors.

### Gate 5: Security & Credentials
- [x] Session tokens use cryptographic hashing and enforce expiration.
- [x] Provider credentials (API keys) are isolated from general task environments.
- [x] Secret sanitization redacts keys and tokens from all log outputs.
- [x] Sudoers file permissions strictly set to `0440` with owner `root:root`.

### Gate 6: Developer Environment & Unity 6
- [x] Loopback HTTP Unity Bridge client communicates with authenticated editor bridge.
- [x] Live Unity 6 batchmode vertical slice passes automated regression testing.
- [x] Automated Unity changes register with Unity Undo stack for reversibility.
- [ ] Desktop application launchers (AI Assistant, Terminal, Files, Settings) launch cleanly.

### Gate 7: Performance & Low-Memory Optimization
- [x] ZRAM compressed swap allocates 50% physical RAM on boot.
- [x] Boot-blocking cloud-init and network-wait units disabled/masked.
- [ ] Idle system RAM consumption verified under 1.4 GB on a 4 GB RAM VM.
- [ ] Cold application launch times verified under 2.0 seconds.

---

## 2. Release Packaging & Verification

- [ ] Rebuild clean ISO using `PyFlare/scripts/fix_and_build_iso.py`.
- [ ] Calculate SHA-256 checksum and save to `pyflare-os-1.0.0-beta-amd64.iso.sha256`.
- [ ] Generate GPG detached signature `pyflare-os-1.0.0-beta-amd64.iso.sig`.
- [ ] Verify ISO boots in a fresh, unconfigured VirtualBox 7.x VM (4 GB RAM, 2 vCPU).
- [ ] Tag git commit as `v1.0.0-beta` and push tags to remote origin.
