"""
branding_generator/previews.py
Generate all 5 preview sheets:
  branding_preview.png  — icon grid
  wallpaper_preview.png — wallpaper thumbnails
  badge_preview.png     — badge grid
  theme_preview.png     — colour palette swatches per theme
  cursor_preview.png    — cursor PNG grid with labels
"""

import os
import logging
from PIL import Image, ImageDraw
from branding_generator.config import THEME_SCHEMES, BRAND_COLORS
from branding_generator.utils import ensure_dir, hex_to_rgb

logger = logging.getLogger("pyflare-brand")

_BG   = hex_to_rgb(BRAND_COLORS["background"])
_SURF = hex_to_rgb(BRAND_COLORS["surface"])
_IND  = hex_to_rgb(BRAND_COLORS["indigo"])
_CYA  = hex_to_rgb(BRAND_COLORS["cyan"])
_WHT  = (255, 255, 255)


def _grid(image_paths: list, output_path: str, cols: int = 4,
          tile_size: int = 128, bg: tuple = None, label: bool = False):
    if not image_paths:
        return
    if bg is None:
        bg = (*_BG, 255)
    rows = (len(image_paths) + cols - 1) // cols
    grid_img = Image.new("RGBA", (cols * tile_size, rows * tile_size), bg)
    for idx, path in enumerate(image_paths):
        if not os.path.exists(path):
            continue
        try:
            with Image.open(path) as tile:
                tile = tile.convert("RGBA")
                tile = tile.resize((tile_size - 12, tile_size - 12), Image.Resampling.LANCZOS)
                x = (idx % cols) * tile_size + 6
                y = (idx // cols) * tile_size + 6
                grid_img.paste(tile, (x, y), tile)
        except Exception:
            pass
    grid_img.save(output_path, "PNG")


def generate_theme_preview(target_root: str, previews_dir: str):
    SWATCH_W  = 80
    SWATCH_H  = 60
    LABEL_H   = 20
    PADDING   = 16
    n_schemes = len(THEME_SCHEMES)
    scheme_list = list(THEME_SCHEMES.items())

    # Colour keys to show as swatches
    swatch_keys = [
        "background", "surface", "primary", "accent",
        "text", "error", "warning", "success",
        "indigo" if "indigo" not in THEME_SCHEMES["dark"] else "primary",
    ]
    # Only use keys that exist in the scheme
    def get_swatches(scheme):
        result = []
        for k in ["background","surface","primary","accent","text","error","warning","success"]:
            if k in scheme:
                result.append((k, scheme[k]))
        return result

    max_swatches = 8
    img_w = PADDING * 2 + (SWATCH_W + 4) * max_swatches
    img_h = PADDING * 2 + (SWATCH_H + LABEL_H + 24) * n_schemes + 40

    img  = Image.new("RGBA", (img_w, img_h), (*_BG, 255))
    draw = ImageDraw.Draw(img)

    # Title strip
    draw.rectangle([0, 0, img_w, 36], fill=(*_IND, 200))

    y_cursor = 48
    for scheme_name, scheme in scheme_list:
        swatches = get_swatches(scheme)[:max_swatches]
        # Scheme label bar
        draw.rectangle([PADDING, y_cursor, img_w - PADDING, y_cursor + LABEL_H],
                        fill=(*_SURF, 200))

        y_cursor += LABEL_H + 4
        for i, (key, hex_val) in enumerate(swatches):
            try:
                r, g, b = hex_to_rgb(hex_val)
            except Exception:
                r, g, b = 128, 128, 128
            sx = PADDING + i * (SWATCH_W + 4)
            sy = y_cursor
            draw.rounded_rectangle([sx, sy, sx + SWATCH_W, sy + SWATCH_H],
                                    radius=8, fill=(r, g, b, 255))
        y_cursor += SWATCH_H + 20

    img.save(os.path.join(previews_dir, "theme_preview.png"), "PNG")


def generate_cursor_preview(target_root: str, previews_dir: str):
    png_dir = os.path.join(target_root, "cursors", "png_preview")
    if not os.path.isdir(png_dir):
        return
    cursor_pngs = sorted(
        os.path.join(png_dir, f) for f in os.listdir(png_dir) if f.endswith(".png")
    )
    _grid(cursor_pngs, os.path.join(previews_dir, "cursor_preview.png"),
          cols=5, tile_size=96)


def generate_all_previews(target_root: str) -> None:
    previews_dir = ensure_dir(os.path.join(target_root, "previews"))

    # 1. Icons / logos
    png_dir = os.path.join(target_root, "logos", "png", "256x256")
    icon_paths = []
    if os.path.isdir(png_dir):
        icon_paths = sorted(
            os.path.join(png_dir, f) for f in os.listdir(png_dir) if f.endswith(".png")
        )
    _grid(icon_paths, os.path.join(previews_dir, "branding_preview.png"),
          cols=4, tile_size=280)

    # 2. Wallpapers
    wp_dir = os.path.join(target_root, "wallpapers")
    wp_paths = []
    if os.path.isdir(wp_dir):
        for wtype in os.listdir(wp_dir):
            type_dir = os.path.join(wp_dir, wtype)
            if os.path.isdir(type_dir):
                for f in os.listdir(type_dir):
                    if f.endswith("_FHD.png"):
                        wp_paths.append(os.path.join(type_dir, f))
    _grid(sorted(wp_paths), os.path.join(previews_dir, "wallpaper_preview.png"),
          cols=2, tile_size=480)

    # 3. Badges
    bg_dir = os.path.join(target_root, "badges")
    bg_paths = []
    if os.path.isdir(bg_dir):
        bg_paths = sorted(
            os.path.join(bg_dir, f) for f in os.listdir(bg_dir) if f.endswith(".png")
        )
    _grid(bg_paths, os.path.join(previews_dir, "badge_preview.png"),
          cols=4, tile_size=180)

    # 4. Theme swatches
    generate_theme_preview(target_root, previews_dir)

    # 5. Cursors
    generate_cursor_preview(target_root, previews_dir)

    logger.info("Previews: generated branding, wallpaper, badge, theme, cursor sheets")
