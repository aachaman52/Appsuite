# PyFlare OS Branding Guide

## Visual Identity

| Element | Value |
|---------|-------|
| Primary color | #3B5BDB (Indigo) |
| Accent color | #00BFFF (Cyan) |
| Secondary | #7C3AED (Violet) |
| Background | #0C0F1E |
| Surface | #0D1117 |
| Text | #E6EDF3 |
| UI Font | Inter 11 |
| Display Font | Space Grotesk Bold |
| Mono Font | JetBrains Mono 11 |

## Generating Assets

All branding assets are **procedurally generated** by `branding_generator/`.

```bash
# Full generation
python -m branding_generator.main generate

# Individual stages
python -m branding_generator.main export
python -m branding_generator.main preview
python -m branding_generator.main validate
```

## Asset Structure

| Directory | Contents |
|-----------|----------|
| `branding/logos/` | SVG + PNG logos |
| `branding/wallpapers/` | 3 resolutions × 8 styles |
| `branding/cursors/` | XCursor, Windows .cur, macOS |
| `branding/themes/` | GTK3/4, Qt, VS Code, Terminal |
| `branding/badges/` | Version badges |
| `branding/icons/` | App icon sizes |
| `branding/animations/` | Lottie JSON, WebP, GIF, MP4 |
| `branding/fonts/` | Font cache + manifest |
| `branding/previews/` | Preview sheets |

## Deploying to Filesystem

```bash
python scripts/copy_branding.py
```
