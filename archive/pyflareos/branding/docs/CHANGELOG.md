# Changelog

## [1.0.0] — 2026-07-29

### Added
- Production-ready SVG-first icon pipeline with `<linearGradient>` / `<radialGradient>` defs
- Proper PDF export via cairosvg (real vector, not text rename)
- Valid EPSF-3.0 wrapper around PostScript output
- Multi-resolution ICO (16–256 px) and ICNS (16–1024 px)
- Pure-Python XCursor binary writer (cross-platform, no xcursorgen)
- Windows `.cur` with PNG-in-ICO embedding + `install.inf`
- macOS cursor PNG exports with `cursor_info.json` hotspot data
- Lottie 5.x JSON animations for all 5 animation types
- MP4 preview generation via imageio/FFmpeg (graceful skip if absent)
- 8 procedural wallpaper types at 3 resolutions each
- Full GTK3/GTK4/Qt/KDE/GNOME/VS Code/Terminal theme engine
- 20+ design tokens per theme scheme (typography, spacing, shadows, animations)
- 6 colour export formats: JSON, CSS, SCSS, QML, TOML, YAML
- Asset validation with SVG XML check, ICO/ICNS magic bytes, JSON parse
- validation_report.json and coloured terminal output
- Manifest with asset_type, supported_platforms, version per asset
- 5 preview sheets: icons, wallpapers, badges, themes, cursors
- Rich documentation: README, CHANGELOG, ASSET_INVENTORY, BRANDING_REPORT
- Incremental build cache (`.build_cache.json`)
- `--jobs`, `--incremental`, `--release` CLI flags
- Per-module timing in GENERATION_STATS.json
- 4 sub-packages (icons, cursors, themes, wallpapers)

### Fixed
- `cairosvg.svg2png` used incorrect `parent_width`/`parent_height` params → fixed to `output_width`/`output_height`
- Windows cursor `.cur` loop referenced source PNGs that were never generated → fixed
- `main.py` `stats` command missing `import json` → fixed
- `--root` was hardcoded to a user-specific path → fixed to `./branding` relative default
- All assets previously contained debug text → removed completely
- EPS/PDF files were renamed SVGs → replaced with proper format conversion

### Changed
- `extras.py` `draw_futuristic_layout()` removed; replaced with `draw_premium_background()`
- All installer, login, social, and UI assets now use glassmorphism + radial gradients
- Wallpapers now generated at 4K/QHD/FHD for each of 8 types
