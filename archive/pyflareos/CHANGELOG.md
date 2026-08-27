# PyFlare OS — Changelog

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [1.0.0] — 2026-07-30 — "Ember"

### Added
- Complete source tree for PyFlare OS 1.0.0 Ember
- Branding generator pipeline (16 modules, 800+ assets)
- Linux filesystem overlay (`filesystem/`)
- 11 application stubs with full structure
- Calamares installer configuration and slides
- Package manifests (core, desktop, applications)
- 14 automated validators + run_all.py
- GitHub Actions CI (build, validate, lint)
- Full documentation suite (8 docs + root docs)
- GNOME gsettings overrides
- GTK3/4 + GNOME Shell dark theme (CSS)
- Plymouth boot splash (script-based)
- GRUB theme with PyFlare branding
- systemd service units

### Changed
- Renamed from AppSuite OS to PyFlare OS throughout
- Vendor updated to Aachman Studios
- Ubuntu base pinned to 24.04 LTS (Noble Numbat)

### Fixed
- Validator Unicode crash on Windows cp1252 terminals
- SVG xmlns false-positive in validator
- cairosvg noise suppression on systems without libcairo

---

## [0.9.0] — 2026-07-29 — "Prototype"

### Added
- Initial branding generator (icons, wallpapers, cursors, themes)
- Basic build scripts
- Initial README

---
