# AppSuite Ecosystem — Known Issues

**Version:** 1.0.0 | **Last Updated:** 2026-08-04 | **Author:** Aachman Studios

---

## PyFlare OS

### KI-001: Live ISO Build Requires Linux Host

**Severity:** Medium | **Status:** By design

`build.py` requires a Linux build environment for chroot, mksquashfs, and xorriso. The branding generator and validators run on Windows/macOS, but the full ISO build does not.

**Workaround:** Use a Ubuntu 24.04 VM or WSL2 for the full build.

---

### KI-002: SquashFS Not Rebuilt on Windows

**Severity:** Low | **Status:** By design

`build/filesystem.squashfs` is a pre-built artefact committed to the repository (207 MB). It may not reflect the latest overlay changes. Rebuild by running `build.py` on Linux.

---

### KI-003: Validator Unicode Crash on Windows (Fixed in v1.0.0)

**Severity:** Low | **Status:** Fixed

On Windows cp1252 terminals, certain Unicode characters in validator output caused `UnicodeEncodeError`. Fixed by adding `encoding='utf-8'` to all file writes and `errors='replace'` to terminal output.

---

### KI-004: cairosvg Warning Without libcairo

**Severity:** Low | **Status:** Suppressed

On systems without libcairo installed, `cairosvg` prints a warning. This does not affect functionality — the branding generator suppresses the warning via `warnings.filterwarnings`.

---

### KI-005: Ollama Service Not Tested Live

**Severity:** Medium | **Status:** Open

The `ollama.service` systemd unit is defined but has not been verified in a live boot environment. It may require adjustment to the `ExecStart` path depending on Ollama's actual install location.

---

### KI-006: Application Stubs Have No Functional UI

**Severity:** Low | **Status:** Known / Planned

All 11 application stubs provide `.desktop` launchers and configuration skeletons but no GTK4 implementation. Clicking them in GNOME will do nothing. GTK4 implementations are planned for v1.1.0 Flare.

---

## AppSuite Jarvis

### KI-007: GraphOrchestrator.run() is Deprecated

**Severity:** Low | **Status:** Deprecated, not yet removed

`GraphOrchestrator.run()` (sequential legacy path) emits a `DeprecationWarning`. It will be removed in a future release. New code uses `run_dag()` exclusively.

---

### KI-008: Blender/Godot Must Be Installed Separately

**Severity:** Medium | **Status:** By design

`BlenderWorker` and `GodotWorker` invoke Blender and Godot 4 as subprocesses. These must be installed and accessible in `PATH` on the machine running Jarvis. They are not included in `requirements.txt`.

---

### KI-009: API Has No Authentication

**Severity:** High | **Status:** Open — development mode only

The FastAPI server at `localhost:8000` has no authentication. Do not expose it to a network without adding authentication middleware.

---

### KI-010: Large Binary Files Removed from Git History

**Severity:** Info | **Status:** Resolved

ISO, VDI, and database snapshot files were previously committed and caused GitHub RPC timeout errors during push. These were removed from git history via `git filter-repo`. The `.gitignore` now prevents future commits of build artefacts.

---

### KI-011: worker_statistics.json is Empty

**Severity:** Low | **Status:** Open

`AppSuite_JarvisV1/worker_statistics.json` contains `{}`. The worker statistics collection was not populated during the last session. This is a non-critical telemetry file.

---

## Related Documents

| Document | Purpose |
|---|---|
| [TECH_DEBT.md](TECH_DEBT.md) | Technical debt register |
| [TODO.md](TODO.md) | Tasks to address issues |
| [BACKLOG.md](BACKLOG.md) | Future fixes |
