# AppSuite Ecosystem — Technical Debt Register

**Version:** 1.0.0 | **Last Updated:** 2026-08-04 | **Author:** Aachman Studios

Technical debt is documented here to maintain awareness and prioritise remediation.

---

## TD-001: GraphOrchestrator.run() Legacy Path

**Area:** AppSuite Jarvis / Engine
**Severity:** Low
**Impact:** Confusing API; risk of accidental use in new code

The legacy sequential `GraphOrchestrator.run()` still exists and emits `DeprecationWarning`. All new code uses `run_dag()` (parallel DAG). The legacy path should be removed after confirming no callers remain.

**Remediation:** Audit all callers, migrate to `run_dag()`, delete `run()`.

---

## TD-002: PyFlare/docs/ Has Duplicate/Stale Content

**Area:** PyFlare / Documentation
**Severity:** Low
**Impact:** Confusion about which docs are authoritative

`PyFlare/docs/` contains 15 legacy documents some of which are now superseded by the root-level `Appsuite/docs/`. Files like `architecture.md`, `DEVELOPMENT.md`, `STYLE_GUIDE.md` exist in both locations.

**Remediation:** Migrate unique content from `PyFlare/docs/` to `Appsuite/docs/`, add deprecation notices, or delete stale files.

---

## TD-003: AppSuite_JarvisV1 Root Has Large Analysis Markdown Files

**Area:** AppSuite Jarvis / Repository hygiene
**Severity:** Low
**Impact:** Clutters repository root; confusing to new contributors

Files like `Analyzing Artisan AI Appsuite.md` (175 KB), `Architectural Review of AppSuite Jarvis.md` (651 KB), `Fixing AppSuite Jarvis Architecture.md` (437 KB) are analysis artefacts from development sessions — not production documentation.

**Remediation:** Move to `AppSuite_JarvisV1/docs/internal/` or remove from repository.

---

## TD-004: setup_tree.py Is Too Large

**Area:** PyFlare / Build System
**Severity:** Medium
**Impact:** Hard to maintain; difficult to test individual sections

`scripts/setup_tree.py` is 102 KB — the largest file in the repository. It handles too many concerns (APT install, Flatpak, Snap, overlay copy, permissions, post-install).

**Remediation:** Decompose into focused modules: `install_apt.py`, `install_snap.py`, `install_flatpak.py`, `apply_overlay.py`, `set_permissions.py`.

---

## TD-005: No API Authentication on Jarvis FastAPI

**Area:** AppSuite Jarvis / Security
**Severity:** High
**Impact:** Jarvis API is open — any process on the machine can submit jobs

The FastAPI server binds to `0.0.0.0:8000` with CORS `allow_origins=["*"]`. In production this is a security risk.

**Remediation:** Add `APIKeyMiddleware` or OAuth2 with `HTTPBearer` tokens before any production deployment.

---

## TD-006: pyflareos/ Directory Contains VirtualBox VM Files

**Area:** PyFlare / Repository hygiene
**Severity:** Low
**Impact:** Confusion between the OS project and a VirtualBox VM

`PyFlare/pyflareos/` contains VirtualBox VM config files (`.vbox`, `.vbox-prev`, unattended install configs). These are development testing artefacts, not source files.

**Remediation:** Add to `.gitignore`, move to a gitignored location, or delete from repository.

---

## TD-007: Empty Document/ Directory

**Area:** Repository root
**Severity:** Very Low
**Impact:** Cosmetic

`Appsuite/Document/` is an empty directory with no purpose currently.

**Remediation:** Delete or add a `README.md` explaining its intended use.

---

## TD-008: worker_statistics.json Is Empty

**Area:** AppSuite Jarvis
**Severity:** Very Low
**Impact:** Telemetry not being collected

`worker_statistics.json` is `{}`. The statistics collection pipeline is not populating it.

**Remediation:** Verify `ObservabilityWriter` is writing statistics; fix collection if broken.

---

## Related Documents

| Document | Purpose |
|---|---|
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Known bugs |
| [TODO.md](TODO.md) | Active tasks |
| [BACKLOG.md](BACKLOG.md) | Future work |
