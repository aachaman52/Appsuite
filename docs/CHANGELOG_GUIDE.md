# AppSuite Ecosystem — Changelog Guide

**Version:** 1.0.0 | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Format

All changelogs follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format and use [Semantic Versioning](https://semver.org/).

---

## Template

```markdown
## [X.Y.Z] — YYYY-MM-DD — "Codename"

### Added
- Feature or document that is new

### Changed
- Existing behaviour that changed

### Fixed
- Bug that was fixed

### Removed
- Feature or file that was deleted

### Deprecated
- Feature marked for future removal

### Security
- Security-related fix
```

---

## Rules

1. One entry per release. Never edit past releases.
2. Unreleased changes go under `## [Unreleased]` at the top.
3. Date format: `YYYY-MM-DD`.
4. Each bullet is one sentence, present tense: "Add animated favicon generation".
5. Link issue numbers: `(#42)`.
6. Breaking changes get a `⚠️ BREAKING:` prefix.

---

## Example Entry

```markdown
## [1.1.0] — 2026-09-01 — "Flare"

### Added
- PyFlare Terminal — VTE-based terminal with Ollama AI completions
- GTK4 AppSuite application connecting to Jarvis FastAPI
- Animated Plymouth boot sequence (rendered flame animation)
- PyFlare Store — Flatpak frontend with PyFlare branding

### Changed
- Plymouth theme upgraded from script-based to video animation
- Ollama service unit updated with correct ExecStart path

### Fixed
- GDM3 login screen not applying PyFlare theming on some hardware

### Deprecated
- `GraphOrchestrator.run()` — will be removed in v1.2.0, use `run_dag()` instead
```

---

## Related Documents

| Document | Purpose |
|---|---|
| [VERSIONING.md](VERSIONING.md) | Version numbering |
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | Release workflow |
