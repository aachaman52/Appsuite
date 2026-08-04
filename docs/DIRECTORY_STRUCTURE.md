# AppSuite Ecosystem — Directory Structure

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Complete Annotated File Tree

```
Appsuite/                                   Repository root
│
├── .gitignore                              Git exclusion rules (Python, IDE, venv, build artefacts)
├── .vscode/
│   └── settings.json                       VS Code workspace settings (git.ignoreLimitWarning)
│
├── docs/                                   ← Root-level documentation (this directory)
│   ├── README.md                           Documentation hub and index
│   ├── SYSTEM_OVERVIEW.md                  Ecosystem overview
│   ├── ARCHITECTURE.md                     Full technical architecture
│   ├── DIRECTORY_STRUCTURE.md              This file
│   ├── REPOSITORY_WALKTHROUGH.md           Guided walkthrough
│   ├── BUILD_PIPELINE.md                   ISO build pipeline
│   ├── BOOT_PROCESS.md                     Boot sequence
│   ├── AI_ARCHITECTURE.md                  Jarvis AI engine
│   ├── ENGINE.md                           Graph orchestrator
│   ├── ORCHESTRATION.md                    Multi-agent coordination
│   ├── BRANDING.md                         Visual identity system
│   ├── FILESYSTEM.md                       Filesystem overlay
│   ├── PACKAGE_SYSTEM.md                   Package management
│   ├── PLUGIN_SYSTEM.md                    Plugin SDK
│   ├── INSTALLER.md                        Calamares installer
│   ├── SECURITY.md                         Security model
│   ├── NETWORKING.md                       Network stack
│   ├── APPLICATION_FRAMEWORK.md            Bundled apps
│   ├── DEVELOPMENT.md                      Developer setup
│   ├── CODING_STANDARD.md                  Code style
│   ├── STYLE_GUIDE.md                      Doc + visual style
│   ├── API_GUIDELINES.md                   API design
│   ├── TESTING.md                          Test suite
│   ├── RELEASE_PROCESS.md                  Release workflow
│   ├── VERSIONING.md                       Version strategy
│   ├── CHANGELOG_GUIDE.md                  Changelog standards
│   ├── PROJECT_STATUS.md                   Completion dashboard
│   ├── CHECKLIST.md                        Master task checklist
│   ├── TODO.md                             Active tasks
│   ├── BACKLOG.md                          Feature backlog
│   ├── MILESTONES.md                       Roadmap milestones
│   ├── KNOWN_ISSUES.md                     Known bugs
│   └── TECH_DEBT.md                        Technical debt
│
├── Document/                               Empty directory (reserved)
│
├── PyFlare/                                PyFlare OS sub-project
│   ├── build.py                            Master ISO build orchestrator (39 KB)
│   ├── audit_script.py                     Repository audit utility (1.8 KB)
│   ├── cleanup_docs.py                     Documentation cleanup utility (3.4 KB)
│   ├── requirements.txt                    Python deps: Pillow, cairosvg, tqdm, pyyaml…
│   ├── index.html                          Project landing page (15 KB)
│   ├── README.md                           Project overview
│   ├── CHANGELOG.md                        Release history
│   ├── ROADMAP.md                          Version roadmap
│   ├── SECURITY.md                         Security policy
│   ├── LICENSE                             PyFlare Proprietary Licence
│   │
│   ├── .github/                            GitHub configuration
│   │   └── workflows/                      GitHub Actions CI pipelines
│   │
│   ├── config/                             OS build configuration
│   │   ├── branding.yaml                   ★ Single source of truth for product identity
│   │   ├── default.yaml                    Build parameters (ISO name, compression, etc.)
│   │   ├── packages.yaml                   APT/Snap/Flatpak package manifest
│   │   ├── theme.yaml                      GTK theme colour tokens
│   │   ├── settings.yaml                   User default settings
│   │   └── post_install.sh                 Post-installation configuration script
│   │
│   ├── branding_generator/                 Procedural brand asset generator
│   │   ├── main.py                         CLI entry point + pipeline orchestrator (10 KB)
│   │   ├── config.py                       Colour tokens + constants (15 KB)
│   │   ├── themes.py                       GTK3/4 + GNOME Shell CSS (28 KB)
│   │   ├── icons.py                        XDG icon theme generator (24 KB)
│   │   ├── wallpapers.py                   4K wallpaper generator (14 KB)
│   │   ├── cursors.py                      X11 cursor theme (18 KB)
│   │   ├── fonts.py                        Font manifests (6 KB)
│   │   ├── animations.py                   Plymouth animation script (17 KB)
│   │   ├── sounds.py                       Sound schema (1.9 KB)
│   │   ├── exporters.py                    Cross-format export (14 KB)
│   │   ├── manifest.py                     Brand manifest JSON (4.4 KB)
│   │   ├── previews.py                     Preview sheets (5.7 KB)
│   │   ├── extras.py                       Badges, social cards, favicons (19 KB)
│   │   ├── utils.py                        Cairo drawing primitives (13 KB)
│   │   ├── validator.py                    Post-generation validation (8.5 KB)
│   │   └── docs.py                         Auto-generated branding docs (9.8 KB)
│   │
│   ├── branding/                           Generated brand assets (800+ files)
│   │   ├── animations/                     Plymouth + UI animations
│   │   ├── badges/                         Repository and product badges
│   │   ├── colors/                         Colour palette exports
│   │   ├── cursors/                        X11 cursor theme
│   │   ├── docs/                           Auto-generated brand docs
│   │   ├── export/                         Cross-format exports (ICO, ICNS)
│   │   ├── favicon/                        Web favicon set
│   │   ├── fonts/                          Font files and manifests
│   │   ├── gtk/                            GTK3/4 theme files
│   │   ├── installer/                      Calamares installer assets
│   │   ├── login/                          GDM login screen assets
│   │   ├── logos/                          SVG and PNG logos
│   │   ├── mockups/                        UI mockup templates
│   │   ├── placeholders/                   Placeholder assets
│   │   ├── previews/                       Preview sheets
│   │   ├── qt/                             Qt/KDE theme files
│   │   ├── screenshots/                    Screenshot templates
│   │   ├── social/                         Social media cards
│   │   ├── sounds/                         Notification sounds
│   │   ├── splash/                         Boot splash images
│   │   ├── store/                          Store listing assets
│   │   ├── themes/                         GNOME Shell + GTK themes
│   │   ├── ui/                             UI component assets
│   │   └── wallpapers/                     Desktop wallpapers (4K)
│   │
│   ├── filesystem/                         Linux root filesystem overlay
│   │   ├── boot/                           GRUB theme, Plymouth config
│   │   ├── etc/                            System configuration files
│   │   │   ├── dconf/                      GNOME settings database
│   │   │   ├── gdm3/                       GDM3 display manager config
│   │   │   ├── systemd/                    Custom service units
│   │   │   └── xdg/                        XDG menu definitions
│   │   ├── home/                           Default user skeleton
│   │   ├── opt/                            PyFlare application bundles
│   │   ├── root/                           Root user configuration
│   │   └── usr/                            Shared data, icons, themes, fonts
│   │       ├── share/
│   │       │   ├── applications/           .desktop files
│   │       │   ├── backgrounds/            Wallpapers
│   │       │   ├── icons/                  Icon themes
│   │       │   ├── plymouth/               Boot splash themes
│   │       │   └── themes/                 GTK themes
│   │       └── bin/                        PyFlare CLI tools
│   │
│   ├── desktop/                            GNOME desktop configuration
│   │   ├── autostart/                      XDG autostart .desktop files
│   │   ├── dock/                           Dash-to-Dock configuration
│   │   ├── gsettings/                      dconf/gsettings overrides
│   │   ├── menus/                          XDG application menu definitions
│   │   └── shortcuts/                      Keyboard shortcut definitions
│   │
│   ├── applications/                       Bundled application stubs
│   │   ├── ai-assistant/                   On-device AI chat (Ollama)
│   │   ├── appsuite/                       AppSuite Jarvis IDE integration
│   │   ├── browser/                        Privacy-focused browser
│   │   ├── engine/                         PyFlare Engine service
│   │   ├── files/                          AI file manager
│   │   ├── launcher/                       Application launcher
│   │   ├── package-manager/                APT/Flatpak/Snap UI
│   │   ├── plugin-manager/                 Plugin management UI
│   │   ├── settings/                       System settings panel
│   │   ├── store/                          Application marketplace
│   │   └── terminal/                       GPU-accelerated terminal
│   │
│   ├── packages/                           Package management
│   │   ├── manifests/                      Per-category package lists
│   │   └── scripts/                        Package installation helpers
│   │
│   ├── installer/                          Calamares installer
│   │   ├── config/                         Calamares module YAML configs
│   │   ├── slides/                         Installation slideshow (HTML/CSS/JS)
│   │   └── README.md                       Installer overview
│   │
│   ├── scripts/                            Build helper scripts (22 files)
│   │   ├── build_iso.py                    ISO remastering (13 KB)
│   │   ├── setup_tree.py                   Rootfs tree setup (102 KB — largest file)
│   │   ├── package_iso.py                  ISO packaging (12 KB)
│   │   ├── package_installer.py            Installer packaging (5.4 KB)
│   │   ├── chroot_manager.py               chroot environment management (4.2 KB)
│   │   ├── download_base.py                Ubuntu ISO downloader (4.7 KB)
│   │   ├── regen_validators.py             Validator regeneration (9.6 KB)
│   │   ├── squashfs_discovery.py           SquashFS analysis (5.4 KB)
│   │   ├── verify_runtime.py               Runtime dependency check (3.6 KB)
│   │   ├── branding.py                     Branding deployment (2.3 KB)
│   │   ├── copy_branding.py                Asset copy helper (1.5 KB)
│   │   ├── clean.py                        Build cleanup (1.8 KB)
│   │   ├── generate_checksums.py           SHA256 checksum generation (1.1 KB)
│   │   ├── generate_manifest.py            Build manifest (1.4 KB)
│   │   ├── install_dependencies.sh         System dependency installer (1.7 KB)
│   │   ├── extract_iso.sh                  ISO extraction (821 B)
│   │   ├── generate_iso.sh                 ISO generation wrapper (966 B)
│   │   ├── fetch_base_iso.sh               Base ISO fetch (281 B)
│   │   ├── chroot_env.sh                   chroot environment script (1.4 KB)
│   │   ├── package_apps.py                 App packaging (886 B)
│   │   ├── prepare_rootfs.py               Rootfs preparation (1.1 KB)
│   │   └── verify_dependencies.py          Dependency verification (1.2 KB)
│   │
│   ├── validation/                         Automated validators (14 files)
│   │   ├── run_all.py                      Validation orchestrator (2.2 KB)
│   │   ├── validate_boot.py                GRUB + Plymouth
│   │   ├── validate_branding.py            Brand assets
│   │   ├── validate_configs.py             YAML/JSON schemas
│   │   ├── validate_desktop.py             Desktop files
│   │   ├── validate_desktop_entries.py     XDG .desktop syntax
│   │   ├── validate_filesystem.py          Required paths
│   │   ├── validate_icons.py               Icon theme
│   │   ├── validate_json.py                JSON parse
│   │   ├── validate_packages.py            Package names
│   │   ├── validate_permissions.py         File permissions
│   │   ├── validate_services.py            systemd units
│   │   ├── validate_svg.py                 SVG structure
│   │   ├── validate_theme.py               GTK theme
│   │   └── validate_wallpapers.py          Wallpaper resolution
│   │
│   ├── tests/                              Test suite
│   │   └── test_squashfs_discovery.py      SquashFS discovery tests (4 KB)
│   │
│   ├── build/                              Build artefacts (gitignored)
│   │   ├── filesystem.squashfs             Compressed rootfs (207 MB)
│   │   ├── iso_extracted/                  Extracted Ubuntu ISO
│   │   └── rootfs/                         Assembled root filesystem
│   │
│   ├── logs/                               Build logs (gitignored)
│   ├── reports/                            Validation reports
│   └── docs/                              Project-level docs (legacy, being migrated)
│       ├── ARCHITECTURE.md
│       ├── BRANDING.md
│       ├── BUILD.md
│       ├── BUILD_CHECKLIST.md
│       ├── CONTRIBUTING.md
│       ├── DEVELOPMENT.md
│       ├── DIRECTORY_STRUCTURE.md
│       ├── FAQ.md
│       ├── INSTALLER.md
│       ├── ISO_BUILD_SYSTEM.md
│       ├── PACKAGING.md
│       ├── RELEASE_CHECKLIST.md
│       ├── STYLE_GUIDE.md
│       ├── architecture.md
│       ├── build_process.md
│       └── customization.md
│
├── AppSuite_JarvisV1/                      AppSuite Jarvis AI engine
│   ├── run_jarvis.py                       CLI entry point (12 KB)
│   ├── requirements.txt                    Python deps: fastapi, langchain, etc.
│   ├── installer.py                        Project installer (4.8 KB)
│   ├── README.md                           Project overview (248 lines)
│   ├── main.gd / main.tscn                 Godot desktop integration
│   ├── project.godot                       Godot project file
│   │
│   ├── config/                             Configuration files
│   │   ├── default_config.yaml             Base system config (615 B)
│   │   ├── user_config.yaml                User overrides (195 B)
│   │   ├── config.json                     Runtime config (1.1 KB)
│   │   ├── config.schema.json              Config JSON schema (1.4 KB)
│   │   ├── providers.json                  LLM provider registry (2 KB)
│   │   └── templates.json                  Scene templates (1.5 KB)
│   │
│   ├── appsuite/                           Core Python package
│   │   ├── __init__.py                     Package version
│   │   ├── main.py                         AppContext + FastAPI factory (8.9 KB)
│   │   ├── config.py                       Config loader (2.8 KB)
│   │   ├── db.py                           SQLite database layer (32 KB)
│   │   ├── models.py                       Pydantic models (1.3 KB)
│   │   ├── logging_setup.py                Structured logging (5.7 KB)
│   │   │
│   │   ├── core/                           Intelligence layer (44 modules)
│   │   ├── agents/                         Specialized agents (10 files)
│   │   ├── engine/                         Execution engine (8 files)
│   │   ├── workers/                        Execution workers (9 files)
│   │   ├── pipeline/                       Job pipeline (pipeline.py 23 KB)
│   │   ├── plugins/                        Plugin system
│   │   ├── api/                            FastAPI routes
│   │   └── graph/                          LangGraph state bridge
│   │
│   ├── scripts/                            Development scripts (15 files)
│   │   ├── assets_v3.py                    Asset pipeline v3 (20 KB)
│   │   ├── test_pipeline_reliability.py    Reliability tests (24 KB)
│   │   ├── test_reliability_v3.py          Reliability v3 (22 KB)
│   │   ├── run_visual_validation.py        Visual validation (10 KB)
│   │   ├── generate_benchmark_report.py    Benchmark reporter (3.7 KB)
│   │   ├── run_audits.py                   Audit runner (2.7 KB)
│   │   ├── validate_real_assets.py         Asset validation (13 KB)
│   │   ├── test_godot_integration.py       Godot integration tests (5.8 KB)
│   │   ├── test_real_assets.py             Real asset tests (4.8 KB)
│   │   ├── validate_project_assets.gd      Godot asset validator (GDScript)
│   │   ├── capture_screen.ps1              Screen capture (PowerShell)
│   │   ├── init_db.py                      Database initialiser (472 B)
│   │   ├── run_job.py                      Single job runner (1.1 KB)
│   │   └── start.sh                        Start script (458 B)
│   │
│   ├── plugins/                            Example plugins
│   │   ├── example_plugin.py               Plugin template (770 B)
│   │   └── sketchfab_plugin.py             Sketchfab asset source (1.3 KB)
│   │
│   ├── tests/                              Pytest suite
│   ├── desktop/                            Desktop integration
│   ├── desktop_ui/                         Desktop UI components
│   ├── output/                             Job output directory
│   └── data/                              Training data
│       └── [dataset files]
│
├── langgraph-main/                         LangGraph vendored dependency
│   ├── README.md                           LangGraph overview (6.5 KB)
│   ├── AGENTS.md                           Agent usage guide (1.9 KB)
│   ├── CLAUDE.md                           Claude-specific notes (1.9 KB)
│   ├── Makefile                            Build and test targets (1.5 KB)
│   ├── .markdownlint.json                  Markdown linting config
│   │
│   ├── docs/                               LangGraph documentation
│   │   ├── llms.txt                        LLM integration notes
│   │   ├── redirects.json                  Doc redirects (28 KB)
│   │   └── generate_redirects.py           Redirect generator
│   │
│   ├── examples/                           Usage examples
│   │
│   └── libs/                               Library source packages
│       ├── langgraph/                      Core StateGraph library
│       │   ├── langgraph/                  Python package
│       │   ├── pyproject.toml              Package metadata
│       │   └── tests/                      Test suite
│       ├── checkpoint/                     Checkpoint interface
│       ├── checkpoint-sqlite/              SQLite checkpoint adapter
│       ├── checkpoint-postgres/            PostgreSQL checkpoint adapter
│       ├── checkpoint-conformance/         Conformance tests
│       ├── prebuilt/                       Pre-built agent patterns
│       ├── cli/                            LangGraph CLI
│       ├── sdk-py/                         Python SDK
│       └── sdk-js/                         JavaScript SDK
│
└── .venv/                                  Python virtual environment (gitignored)
```

---

## Key Files Reference

| File | Size | Purpose |
|---|---|---|
| `PyFlare/build.py` | 39 KB | Master ISO build orchestrator |
| `PyFlare/scripts/setup_tree.py` | 102 KB | Rootfs tree builder (largest file) |
| `AppSuite_JarvisV1/appsuite/db.py` | 32 KB | Full SQLite schema and queries |
| `AppSuite_JarvisV1/appsuite/core/jarvis.py` | 35 KB | JarvisCore orchestration |
| `AppSuite_JarvisV1/appsuite/core/jarvis_brain.py` | 21 KB | LLM-based planner |
| `AppSuite_JarvisV1/appsuite/workers/internet_worker.py` | 30 KB | Asset download engine |
| `AppSuite_JarvisV1/appsuite/workers/blender_worker.py` | 26 KB | Blender pipeline |
| `AppSuite_JarvisV1/appsuite/workers/godot_worker.py` | 22 KB | Godot project builder |
| `PyFlare/branding/manifest.json` | 318 KB | Full brand manifest |
| `PyFlare/branding/validation_report.json` | 62 KB | Last validation report |

---

## Related Documents

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture and component relationships |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | How the ISO is built |
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | Jarvis engine internals |
| [BRANDING.md](BRANDING.md) | Branding generator detail |
| [FILESYSTEM.md](FILESYSTEM.md) | Filesystem overlay detail |
