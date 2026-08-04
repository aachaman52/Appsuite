# AppSuite Ecosystem — Branding System

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

PyFlare OS ships a complete, coherent visual identity generated entirely by code. No assets are hand-crafted — every logo, icon, wallpaper, cursor, theme, and animation is produced by the `branding_generator/` Python pipeline reading `config/branding.yaml`.

**Generated output:** 800+ files across 24 categories in `branding/`.

---

## Brand Identity

| Token | Value |
|---|---|
| Product name | PyFlare OS |
| Codename | Ember |
| Version | 1.0.0 |
| Developer | Aachman Studios |
| Tagline | "The AI-Native Linux Distribution" |
| Homepage | https://pyflare.dev |
| Support | https://aachmanstudios.dev/support |

---

## Brand Colours

All colours are defined in `config/branding.yaml` and `branding_generator/config.py`:

| Token | Usage |
|---|---|
| Primary accent | PyFlare flame orange-red |
| Background dark | Near-black surface |
| Surface | Elevated dark panels |
| On-primary | White text on accent |
| On-surface | Light text on surfaces |

---

## Generator Modules

| Module | Output Directory | Description |
|---|---|---|
| `themes.py` | `branding/themes/`, `branding/gtk/`, `branding/qt/` | GTK3/4 CSS, GNOME Shell CSS, Qt palette |
| `icons.py` | `branding/logos/`, `branding/favicon/` | SVG master logo + PNG rasters, favicons |
| `wallpapers.py` | `branding/wallpapers/` | 4K dark wallpapers with flame motif |
| `cursors.py` | `branding/cursors/` | X11 Xcursor theme (all standard cursors) |
| `fonts.py` | `branding/fonts/` | Font manifests (Inter, Space Grotesk, JetBrains Mono) |
| `animations.py` | `branding/animations/`, `branding/splash/` | Plymouth boot animation, UI transitions |
| `sounds.py` | `branding/sounds/` | Notification sound schema |
| `exporters.py` | `branding/export/` | ICO (Windows), ICNS (macOS), WebP |
| `manifest.py` | `branding/manifest.json` | Complete brand manifest (318 KB) |
| `previews.py` | `branding/previews/` | Preview sheets showing all assets |
| `extras.py` | `branding/badges/`, `branding/social/`, `branding/screenshots/` | GitHub badges, social cards, mockups |
| `docs.py` | `branding/docs/` | Auto-generated branding documentation |

---

## Running the Branding Generator

```bash
cd PyFlare/

# Generate all assets
python -m branding_generator.main generate

# Validate generated assets
python -m branding_generator.main validate

# Generate specific module only
python -m branding_generator.main generate --module icons
python -m branding_generator.main generate --module themes
python -m branding_generator.main generate --module wallpapers
```

---

## Asset Deployment

During the ISO build, branding assets are deployed into the filesystem overlay by `scripts/copy_branding.py`:

| Source | Destination in rootfs | Purpose |
|---|---|---|
| `branding/themes/` | `/usr/share/themes/PyFlare-Dark/` | GTK theme |
| `branding/logos/svg/` | `/usr/share/pixmaps/pyflare.svg` | App icon |
| `branding/wallpapers/` | `/usr/share/backgrounds/pyflare/` | Wallpapers |
| `branding/cursors/` | `/usr/share/icons/PyFlare-Cursors/` | Cursor theme |
| `branding/fonts/` | `/usr/share/fonts/pyflare/` | Brand fonts |
| `branding/splash/` | `/usr/share/plymouth/themes/pyflare/` | Boot splash |
| `branding/gtk/` | `/usr/share/gnome-shell/theme/pyflare/` | GNOME Shell theme |
| `branding/installer/` | Calamares branding path | Installer UI |

---

## Installer Branding

Calamares (the graphical installer) reads branding from `branding/installer/` and `installer/`:

| Asset | Purpose |
|---|---|
| `branding/installer/logo.png` | Installer sidebar logo |
| `branding/installer/background.png` | Installer background |
| `installer/slides/` | Installation slideshow (HTML/CSS/JS) |

---

## Fonts

PyFlare OS uses three purpose-selected typefaces:

| Font | Usage | Source |
|---|---|---|
| **Inter** | UI text, body copy | Google Fonts |
| **Space Grotesk** | Headings, brand text | Google Fonts |
| **JetBrains Mono** | Code, terminal | JetBrains |

Fonts are defined in `config/default.yaml`:
```yaml
desktop:
  font_ui:      "Inter 11"
  font_heading: "Space Grotesk 12"
  font_mono:    "JetBrains Mono 11"
```

---

## Validation

`branding/validation_report.json` (62 KB) contains the last full validation run output. The validator checks:

- All expected asset categories present
- SVG files have correct namespaces
- PNG files meet minimum resolution requirements
- Theme files have required keys
- Cursor theme has all standard cursor names
- Manifest JSON is valid and complete

---

## Related Documents

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | Build pipeline |
| [FILESYSTEM.md](FILESYSTEM.md) | Where assets land in the OS |
| [BOOT_PROCESS.md](BOOT_PROCESS.md) | Plymouth and GRUB theming |
