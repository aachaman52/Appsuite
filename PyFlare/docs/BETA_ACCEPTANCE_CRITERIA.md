# PyFlare OS — Beta 1.0 Acceptance Criteria

**Target Release Date:** 2 February 2027  
**Document Status:** Release Gate Reference  
**Applicable Edition:** PyFlare for Game Developers  

---

## 1. General Principles

To achieve Beta 1.0 sign-off, every acceptance criterion defined below must be empirically validated on target hardware (VirtualBox 7.x, 4 GB RAM, 2 vCPUs, SSD virtual disk).

---

## 2. Release Gate Acceptance Matrix

### Gate 1: Bootable and Installable Operating System
- **AC-1.1 (ISO Assembly):** Build pipeline produces a valid hybrid ISO image (`pyflare-os-1.0.0-beta-amd64.iso`) bootable via BIOS and UEFI.
- **AC-1.2 (Cold Boot):** System boots from ISO to an interactive GNOME desktop in under 45 seconds without user intervention.
- **AC-1.3 (Zero Boot Hangs):** Zero kernel watchdogs, soft lockups, or debconf blocking loops during boot.
- **AC-1.4 (First-Boot Flow):** `pyflare-firstrun` launches on initial live boot, runs hardware profiling, records state in `/var/lib/pyflare/.firstrun-complete`, and exits cleanly.
- **AC-1.5 (Calamares Installation):** Calamares offline installer successfully formats a virtual disk (ext4 + EFI system partition), copies the rootfs, configures GRUB, and reboots cleanly into the installed OS.

### Gate 2: Hardware-Aware Intelligence
- **AC-2.1 (Hardware Detection):** Detects total RAM, CPU core count, GPU model, and dedicated VRAM with 100% precision.
- **AC-2.2 (Conservative Tier Assignment):** Systems with < 8 GB RAM or missing dedicated GPU are automatically assigned `ModelTier.API_ONLY` or `ModelTier.MINIMAL`.
- **AC-2.3 (Storage Pre-flight):** Model downloads fail immediately with actionable explanations if free disk space is less than required model size + 1 GB safety buffer.
- **AC-2.4 (Profiling Caching):** Hardware snapshot caching reduces repeated query latency from > 500 ms to < 10 ms.

### Gate 3: Control Plane & Task Routing
- **AC-3.1 (TaskSpec Enforcement):** All user and agent requests conform to the strictly typed `TaskSpec` schema. Disallowed types or unknown fields are rejected with structured error codes.
- **AC-3.2 (Deterministic Routing):** Identical task specs and hardware states yield identical routing decisions.
- **AC-3.3 (Offline Isolation):** When network state is offline or task privacy is `LOCAL_ONLY`, cloud providers are strictly filtered from the routing pool.
- **AC-3.4 (Tool Priority):** Deterministic local tools always outrank speculative LLM calls when a capability match exists.

### Gate 4: Execution Engine & Lifecycle
- **AC-4.1 (State Machine):** Tasks transition through `PENDING -> ADMITTED -> RUNNING -> COMPLETED` (or `FAILED`) with state recorded in SQLite `journal.sqlite3`.
- **AC-4.2 (Idempotency):** Submitting a task with a duplicate `task_id` returns the existing result without executing duplicate work.
- **AC-4.3 (Audit Trail):** Every execution request, admitted grant, route decision, and result summary is recorded in append-only JSON Lines format (`audit.jsonl`).
- **AC-4.4 (Timeout Enforcement):** Stalled or hung worker processes are automatically terminated upon exceeding `TaskSpec.timeout_seconds`.

### Gate 5: Authentication & Security
- **AC-5.1 (User Authentication):** Session tokens are securely hashed and validated. Expired or forged tokens reject execution immediately.
- **AC-5.2 (Credential Isolation):** Third-party AI API keys (OpenAI, Anthropic, HuggingFace) are stored in encrypted, isolated keyrings inaccessible to unprivileged guest processes.
- **AC-5.3 (Secret Redaction):** All logging and error reporting sinks redact API keys, bearer tokens, and passwords using pattern-based masking.
- **AC-5.4 (Least Privilege):** Daemons (`pyflare-engine`) run with non-root privileges where possible, and transient sudo permissions are restricted to system configuration tasks.

### Gate 6: Developer Environment & Unity 6
- **AC-6.1 (Unity Editor Bridge):** The PyFlare Unity bridge (`com.aachmanstudios.pyflare.automation`) connects via loopback HTTP (`127.0.0.1:47831`) with token-based authentication.
- **AC-6.2 (Live Automation):** Real vertical slice operations (`game_object.create`, `scene.modify`) execute in Unity 6000.0.69f1+ and return verified `GlobalObjectId` identifiers.
- **AC-6.3 (Undo Safeguards):** All automated Unity operations register with the Unity Undo system, enabling complete developer rollback in the editor.
- **AC-6.4 (Developer Toolchain):** Python 3.12+, Git, Build-Essential, and VS Code OSS or GNOME Builder are available in the default environment.

### Gate 7: Performance & Low-Memory Targets
- **AC-7.1 (RAM Baseline):** On a 4 GB RAM VM, system idle memory consumption after desktop load is < 1.4 GB.
- **AC-7.2 (Swap Management):** ZRAM swap is automatically provisioned at 50% physical RAM (2 GB on a 4 GB system) with zstd compression active.
- **AC-7.3 (CPU Idle):** Background daemon CPU utilization is < 2.0% when the system is idle.
- **AC-7.4 (Interactive Latency):** Terminal, file manager, and launcher open within 1.5 seconds of click event under 4 GB RAM.
