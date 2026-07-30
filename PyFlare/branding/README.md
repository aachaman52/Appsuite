# PyFlare Branding System

**Version 1.0.0** · Generated 2026-07-29

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
| Primary | Electric Indigo `#5B5FFF` |
| Accent | Vibrant Cyan `#00D4FF` |
| Violet | Deep Violet `#8A5CF5` |
| Background | Matte Navy `#0B0F19` |
| Surface | Card Surface `#111827` |
| UI Font | Inter |
| Heading Font | Space Grotesk |
| Mono Font | JetBrains Mono |

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
