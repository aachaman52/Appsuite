# Archive & Deletion Manifest (ARCHIVE_MANIFEST.md)

This manifest records every file and directory moved to `archive/` or removed from the repository during the PyFlare production-readiness refactor.

**Date:** 2026-08-27  
**Branch:** `refactor/pyflare-cleanup`  
**Canonical Product Name:** PyFlare  

---

## Summary of Changes

| Category | Source Path | Destination / Status | Purpose / Rationale | Replacement / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Vendored Dependency** | `langgraph-main/` | **DELETED** | Unmodified copy of upstream LangGraph repository. | Use standard `langgraph` package via `pyproject.toml` if needed. |
| **OS Builder / ISO Scripts** | `PyFlare/pyflareos/` | `archive/pyflareos/pyflareos/` | VirtualBox VM and ISO unattended build scripts. | Archived for reference. |
| **OS Builder / Filesystem** | `PyFlare/filesystem/` | `archive/pyflareos/filesystem/` | Root filesystem overlay for Ubuntu ISO build (fstab, plymouth, systemd). | Archived for reference. |
| **OS Builder / Desktop & Calamares** | `PyFlare/desktop/`, `PyFlare/installer/`, `PyFlare/packages/` | `archive/pyflareos/` | Calamares installer slides, desktop entries, package lists. | Archived for reference. |
| **OS Builder / Branding Gen** | `PyFlare/branding_generator/`, `PyFlare/branding/` | `archive/pyflareos/branding_generator/` | Procedural wallpaper/icon/theme generation for OS ISO. | Archived for reference. |
| **OS Builder / Build Scripts** | `PyFlare/build.py`, `PyFlare/scripts/`, `PyFlare/validation/`, `PyFlare/tests/` | `archive/pyflareos/` | Ubuntu ISO build and squashfs validation scripts. | Archived for reference. |
| **OS Builder / App Skeletons** | `PyFlare/applications/` | `archive/pyflareos/applications/` | Empty application GUI skeletons created for OS mock. | Functional AI engine consolidated in `src/pyflare/`. |
| **Media / Marketing** | `trailer_app/`, `*.mp4`, `*.png` | `archive/media/` | Marketing video renders, HTML trailer mock, raw video frames. | Archived; untracked binary media excluded via `.gitignore`. |
| **Outdated Chat Logs / AI Dumps** | `Fixing AppSuite Jarvis Architecture.md`, `Analyzing Artisan AI Appsuite.md`, `Architectural Review of AppSuite Jarvis.md`, `Audit by 17.7.26`, `AppSuite_JarvisV1/*.md` | `archive/docs/` | AI dialogue dumps, duplicate architectural transcripts, old audit logs. | Consolidated accurate documentation created in `docs/` and `README.md`. |
| **Legacy Godot / UI Mockups** | `AppSuite_JarvisV1/main.gd`, `AppSuite_JarvisV1/main.tscn`, `AppSuite_JarvisV1/project.godot`, `desktop/`, `desktop_ui/` | `archive/legacy_ui/` | Early Godot UI experiment (also contained hardcoded test API key). | Hardcoded API keys scrubbed; archived. |
| **Benchmark Logs / Run Output** | `AppSuite_JarvisV1/agent_timeline.json`, `execution_metrics.json`, `execution_timeline.json`, `worker_statistics.json`, `pytest_last_run.txt` | `archive/data/` | Ephemeral test/benchmark artifacts. | Standard pytest & benchmark suite in `tests/`. |

---

## Detailed Component Manifest

### 1. Vendored Libraries
- **`langgraph-main/`**
  - *Description:* Vendored source code of `langgraph`.
  - *Action:* Deleted.
  - *Verification:* Verified not locally modified. Declared in standard Python packaging if required.

### 2. PyFlare OS ISO Builder (`PyFlare/`)
- **`PyFlare/pyflareos/`**: VirtualBox unattended configs (`.vbox`, `.viso`, `vboxpostinstall.sh`).
- **`PyFlare/branding_generator/`**: Python scripts for procedural SVG/PNG/Theme creation.
- **`PyFlare/filesystem/`**: Debian/Ubuntu `/etc` and `/usr` overlay trees.
- **`PyFlare/installer/`**: Calamares installer configurations and QML slides.
- **`PyFlare/desktop/`**: XFCE/GNOME desktop configurations and `.desktop` files.
- **`PyFlare/packages/`**: APT package selection lists.
- **`PyFlare/validation/`**: OS build sanity checks (`validate_boot.py`, `validate_theme.py`, etc.).
- **`PyFlare/build.py` & `PyFlare/scripts/`**: Orchestration scripts for extracting and repacking Ubuntu ISOs.
- *Action:* Moved to `archive/pyflareos/`.

### 3. Media & Trailer Assets
- **`Aachman_Studios_Ecosystem_Trailer.mp4`**, **`test_*.mp4`**, **`aachmanstiudios.png`**, **`render_trailer_mp4.py`**
- **`trailer_app/`**: Standalone web player for trailer storyboard.
- *Action:* Moved to `archive/media/`.

### 4. Legacy AI Transcripts & Duplicate Audits
- **`Fixing AppSuite Jarvis Architecture.md`** (Root and subfolder copies)
- **`Analyzing Artisan AI Appsuite.md`**
- **`Architectural Review of AppSuite Jarvis.md`**
- **`Audit by 17.7.26`**
- **`AppSuite_JarvisV1/reliability_report.md`**, `pipeline_reliability_v2.md`, `pipeline_reliability_v3.md`, `godot_integration_report.md`
- *Action:* Moved to `archive/docs/`.

### 5. Active Code Migration
- **`AppSuite_JarvisV1/appsuite/`** -> **`src/pyflare/`**
  - All functional agent implementations (`agents/`), API (`api/`), core runtime (`core/`), memory subsystems (`memory/`), pipeline & assets (`pipeline/`), plugins (`plugins/`), providers (`providers/`), scheduler (`scheduler/`), and workers (`workers/`) are preserved, updated to canonical `pyflare` naming, and hardened.
