# AppSuite Ecosystem — Testing

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

Testing in the AppSuite ecosystem spans two categories: validation suites for PyFlare OS build integrity, and pytest-based testing for AppSuite Jarvis.

---

## PyFlare OS — Validation Suite

**Location:** `PyFlare/validation/`

### Running All Validators

```bash
python PyFlare/validation/run_all.py
```

`run_all.py` executes all 14 validators in sequence and reports a pass/fail summary. Any failure aborts the build pipeline.

### Validator Reference

| Validator | File | What It Checks |
|---|---|---|
| Boot | `validate_boot.py` | GRUB config syntax, Plymouth theme files present |
| Branding | `validate_branding.py` | Logo SVG, wallpapers, icon theme directory |
| Configs | `validate_configs.py` | YAML schema validity for all config files |
| Desktop | `validate_desktop.py` | Desktop config files and autostart entries |
| Desktop Entries | `validate_desktop_entries.py` | XDG .desktop file syntax (Name, Exec, Icon fields) |
| Filesystem | `validate_filesystem.py` | Required overlay paths exist |
| Icons | `validate_icons.py` | Icon theme has all required sizes |
| JSON | `validate_json.py` | All JSON files parse without error |
| Packages | `validate_packages.py` | Package names are valid APT identifiers |
| Permissions | `validate_permissions.py` | Executable permissions on scripts |
| Services | `validate_services.py` | systemd unit files parse correctly |
| SVG | `validate_svg.py` | SVG xmlns namespace, no broken references |
| Theme | `validate_theme.py` | GTK theme has index.theme + required files |
| Wallpapers | `validate_wallpapers.py` | Wallpaper PNG meets minimum 1920×1080 resolution |

### SquashFS Discovery Tests

```bash
pytest PyFlare/tests/test_squashfs_discovery.py -v
```

Tests the `scripts/squashfs_discovery.py` module which analyses the contents of the built `filesystem.squashfs`.

---

## AppSuite Jarvis — Test Suite

**Location:** `AppSuite_JarvisV1/tests/` and `AppSuite_JarvisV1/scripts/`

### Running Tests

```bash
cd AppSuite_JarvisV1
pytest tests/ -v
```

### Script-Level Tests

| Script | Coverage | Size |
|---|---|---|
| `scripts/test_pipeline_reliability.py` | Full pipeline end-to-end reliability | 24 KB |
| `scripts/test_reliability_v3.py` | v3 reliability with 100-asset stress test | 22 KB |
| `scripts/test_godot_integration.py` | Godot subprocess integration | 5.8 KB |
| `scripts/test_real_assets.py` | Real asset download and processing | 4.8 KB |
| `scripts/validate_real_assets.py` | Asset validation pipeline | 13 KB |
| `scripts/run_audits.py` | Security and code audits | 2.7 KB |

### Benchmark Report

```bash
python scripts/generate_benchmark_report.py
```

Produces a report covering:
- Task success/failure rates per agent type
- Average execution times per worker
- Memory usage peaks
- Provider call success rates

---

## Test Status

| Category | Count | Status |
|---|---|---|
| Jarvis unit tests | 340+ | ✅ Passing |
| Pipeline reliability (100 assets) | 100 | ✅ 94.2% success rate |
| Godot integration | Multiple | ✅ Passing |
| OS validators | 14 | ✅ All passing |
| SquashFS discovery | Several | ✅ Passing |

---

## CI Integration

Tests run automatically via GitHub Actions on every push and PR. See `PyFlare/.github/workflows/` for CI pipeline definitions.

---

## Related Documents

| Document | Purpose |
|---|---|
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | How validation integrates with build |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developer setup |
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code quality standards |
