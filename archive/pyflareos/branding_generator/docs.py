"""
branding_generator/docs.py
Generates README.md, CHANGELOG.md, ASSET_INVENTORY.md,
BRANDING_REPORT.md, LICENSE, and GENERATION_STATS.json.
"""

import os
import json
import logging
from datetime import datetime
from branding_generator.config import VERSION, BRAND_COLORS, TYPOGRAPHY, GRADIENT_DEFINITIONS
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")


def generate_documentation_files(target_root: str, stats: dict = None) -> None:
    docs_dir = ensure_dir(os.path.join(target_root, "docs"))
    now      = datetime.now().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # README.md (at branding root)
    # ------------------------------------------------------------------
    readme = f"""# PyFlare Branding System

**Version {VERSION}** · Generated {now}

The complete visual identity and branding pipeline for the PyFlare ecosystem.
Every asset is auto-generated from source — reproducible, consistent, and production-ready.

## Directory Structure

| Directory | Contents |
|-----------|----------|
| `logos/` | SVG source icons + multi-size PNG exports (16 → 1024 px) |
| `export/` | Per-icon PDF, EPS, PNG, ICO, ICNS packages |
| `wallpapers/` | Procedural 4K / QHD / FHD wallpapers (8 types) |
| `cursors/linux/` | XCursor theme (pure-Python binary, no xcursorgen required) |
| `cursors/windows/` | Windows `.cur` files + `install.inf` |
| `cursors/macos/` | macOS cursor PNGs with `cursor_info.json` hotspot data |
| `animations/` | PNG sequences, WebP, GIF, Lottie JSON, MP4 previews |
| `themes/` | GTK3/GTK4 CSS, Qt QSS, KDE .colors, GNOME terminal, VS Code |
| `colors/` | JSON, CSS, SCSS, QML, TOML, YAML colour tokens |
| `sounds/` | WAV sound theme files |
| `fonts/` | Inter, Space Grotesk, JetBrains Mono + `font_manifest.json` |
| `badges/` | SVG + PNG ecosystem badges |
| `favicon/` | ICO, multi-size PNGs, apple-touch-icon |
| `social/` | Platform-specific banner assets |
| `installer/` | Installer state cards + background |
| `login/` | Login/lockscreen backgrounds + avatars |
| `previews/` | Auto-generated preview sheets |
| `docs/` | This documentation |

## Visual Standards

| Token | Value |
|-------|-------|
| Primary | Electric Indigo `{BRAND_COLORS["indigo"]}` |
| Accent | Vibrant Cyan `{BRAND_COLORS["cyan"]}` |
| Violet | Deep Violet `{BRAND_COLORS["violet"]}` |
| Background | Matte Navy `{BRAND_COLORS["background"]}` |
| Surface | Card Surface `{BRAND_COLORS["surface"]}` |
| UI Font | {TYPOGRAPHY["primary"]} |
| Heading Font | {TYPOGRAPHY["headings"]} |
| Mono Font | {TYPOGRAPHY["monospace"]} |

## Regenerating Assets

```bash
# Full rebuild
python -m branding_generator.main generate

# Incremental build (skip unchanged)
python -m branding_generator.main generate --incremental

# Validate outputs
python -m branding_generator.main validate

# Package release ZIPs
python -m branding_generator.main package

# Show stats
python -m branding_generator.main stats
```

## Requirements

```
Pillow >= 10.0  cairosvg >= 2.7  tqdm  colorama  numpy  requests
imageio[ffmpeg]  icnsutil
```
"""
    with open(os.path.join(target_root, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    # ------------------------------------------------------------------
    # CHANGELOG.md
    # ------------------------------------------------------------------
    changelog = f"""# Changelog

## [{VERSION}] — {now}

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
"""
    with open(os.path.join(docs_dir, "CHANGELOG.md"), "w", encoding="utf-8") as f:
        f.write(changelog)

    # ------------------------------------------------------------------
    # LICENSE
    # ------------------------------------------------------------------
    license_txt = f"""PyFlare Proprietary Design License
Version {VERSION} — {now}

Copyright (c) 2026 PyFlare Project. All rights reserved.

All branding designs, logos, wallpapers, icons, cursors, sounds, animations,
and other assets in this repository are the proprietary property of the PyFlare
developers unless explicitly documented otherwise.

Permission is NOT granted to use, copy, modify, distribute, or sublicense
these assets for any purpose without prior written permission from the
PyFlare project maintainers.

THE ASSETS ARE PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
"""
    with open(os.path.join(docs_dir, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(license_txt)

    # ------------------------------------------------------------------
    # ASSET_INVENTORY.md (built from manifest.json if present)
    # ------------------------------------------------------------------
    manifest_path = os.path.join(target_root, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as mf:
            manifest = json.load(mf)
        assets = manifest.get("assets", {})
        inv_lines = [
            "# Asset Inventory\n",
            f"Total assets: **{len(assets)}**\n",
            f"Generated: {now}\n\n",
            "| Path | Type | Size | Dimensions | Platforms |\n",
            "|------|------|------|------------|----------|\n",
        ]
        for rel, meta in sorted(assets.items()):
            dims  = meta.get("dimensions") or "—"
            size  = f"{meta.get('size_bytes', 0):,} B"
            atype = meta.get("asset_type", "—")
            plats = ", ".join(meta.get("supported_platforms", ["universal"]))
            inv_lines.append(f"| `{rel}` | {atype} | {size} | {dims} | {plats} |\n")
        with open(os.path.join(docs_dir, "ASSET_INVENTORY.md"), "w", encoding="utf-8") as f:
            f.writelines(inv_lines)

    # ------------------------------------------------------------------
    # BRANDING_REPORT.md
    # ------------------------------------------------------------------
    report = f"""# PyFlare Branding Report
**Version {VERSION}** · {now}

## Colour Palette

| Name | Hex | RGB |
|------|-----|-----|
"""
    for name, hex_val in BRAND_COLORS.items():
        h = hex_val.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        report += f"| {name} | `{hex_val}` | {r}, {g}, {b} |\n"

    report += "\n## Gradients\n\n"
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        stops = " → ".join(f"`{s['color']}`" for s in gdef["stops"])
        report += f"- **{gname}**: {gdef['type']} {stops}\n"

    report += f"""
## Typography

| Role | Font |
|------|------|
| UI / Body | {TYPOGRAPHY["primary"]} |
| Headings | {TYPOGRAPHY["headings"]} |
| Monospace / Code | {TYPOGRAPHY["monospace"]} |

## Theme Schemes

| Scheme | Variant | Primary | Accent |
|--------|---------|---------|--------|
"""
    from branding_generator.config import THEME_SCHEMES
    for sname, scheme in THEME_SCHEMES.items():
        report += f"| {sname} | {scheme.get('variant','—')} | `{scheme.get('primary','—')}` | `{scheme.get('accent','—')}` |\n"

    with open(os.path.join(docs_dir, "BRANDING_REPORT.md"), "w", encoding="utf-8") as f:
        f.write(report)

    # ------------------------------------------------------------------
    # GENERATION_STATS.json
    # ------------------------------------------------------------------
    if stats:
        with open(os.path.join(docs_dir, "GENERATION_STATS.json"), "w") as f:
            json.dump(stats, f, indent=2)

    logger.info("Docs: README, CHANGELOG, LICENSE, ASSET_INVENTORY, BRANDING_REPORT generated")
