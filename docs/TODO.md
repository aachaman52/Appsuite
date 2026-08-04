# AppSuite Ecosystem — Active TODO

**Version:** 1.0.0 | **Last Updated:** 2026-08-04 | **Author:** Aachman Studios

This document tracks actionable tasks currently in progress or next to be started. For the complete project task list, see [CHECKLIST.md](CHECKLIST.md).

---

## Critical / Blocking

- [ ] **Set up self-hosted Linux runner** for GitHub Actions ISO build workflow. Without this, the full ISO cannot be built automatically.
- [ ] **Boot-test PyFlare OS 1.0.0 Ember** in a VM (VirtualBox or QEMU) on a Linux host to validate the full boot sequence.
- [ ] **Verify Ollama service unit** starts correctly after live ISO boot — `systemctl status ollama`.

---

## High Priority

- [ ] **Implement AppSuite GTK4 application** (v1.1.0 Flare): UI shell connecting to Jarvis FastAPI at `localhost:8000`. Priority: prompt input + job progress view.
- [ ] **Implement PyFlare Terminal** (v1.1.0 Flare): VTE-based terminal with Ollama AI command completions.
- [ ] **Add API authentication** to AppSuite Jarvis FastAPI. Currently open (development mode).
- [ ] **Configure Dependabot** for both `PyFlare/requirements.txt` and `AppSuite_JarvisV1/requirements.txt`.
- [ ] **Add root CONTRIBUTING.md** explaining the contribution workflow for the whole repository.

---

## Medium Priority

- [ ] **GitHub issue templates**: bug report and feature request templates in `.github/ISSUE_TEMPLATE/`.
- [ ] **Pin requirements.txt versions** for AppSuite_JarvisV1 to the tested set.
- [ ] **Add Bandit security scan** to the CI lint pipeline for AppSuite Jarvis.
- [ ] **Plymouth animated sequence** (v1.1.0 Flare): replace script-based splash with a rendered flame animation.
- [ ] **GRUB background image**: generate a rendered background image (currently using colour fills).

---

## Low Priority

- [ ] **Clean up legacy docs in PyFlare/docs/**: migrate remaining project-level content to `Appsuite/docs/` and remove duplicates.
- [ ] **Delete empty `Document/` directory** from repository root.
- [ ] **Add `.editorconfig`** at repository root for cross-editor consistency.
- [ ] **LangGraph upgrade**: check if `langgraph-main/` vendored copy is up to date with upstream.

---

## Completed This Sprint

- [x] Created `Appsuite/docs/` with 30+ production-quality documentation files
- [x] Completed all 14 PyFlare OS validators
- [x] Completed AppSuite Jarvis Phases 1–11
- [x] Full branding generator pipeline (16 modules, 800+ assets)

---

## Related Documents

| Document | Purpose |
|---|---|
| [BACKLOG.md](BACKLOG.md) | Longer-term feature backlog |
| [MILESTONES.md](MILESTONES.md) | Milestone planning |
| [CHECKLIST.md](CHECKLIST.md) | Full task list |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Known bugs |
