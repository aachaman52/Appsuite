"""
branding_generator/wallpapers.py
Procedural wallpaper generation for PyFlare.

8 wallpaper types generated at 3 resolutions (4K, QHD, FHD).
Uses numpy for fast pixel operations where available; falls back to PIL.

Types:
  default_dark  — sine-wave glow ribbons
  aurora        — diagonal wavy bands (violet)
  abstract_blue — frequency interference grid
  minimal_dark  — subtle centered radial glow
  nebula        — Perlin-like layered noise clouds
  circuit       — procedural circuit-board traces
  geometric     — tiled hexagonal gradient grid
  deep_space    — star field + nebula halos
"""

import os
import math
import logging
import random

from PIL import Image, ImageDraw, ImageFilter
from branding_generator.config import BRAND_COLORS, WALLPAPER_TYPES, WALLPAPER_RESOLUTIONS
from branding_generator.utils import ensure_dir, ProgressReporter, hex_to_rgb

logger = logging.getLogger("pyflare-brand")

_IND = hex_to_rgb(BRAND_COLORS["indigo"])
_CYA = hex_to_rgb(BRAND_COLORS["cyan"])
_VIO = hex_to_rgb(BRAND_COLORS["violet"])
_PRI = hex_to_rgb(BRAND_COLORS["primary"])
_BG  = hex_to_rgb(BRAND_COLORS["background"])


def _try_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Render at small scale then upscale (performance optimisation)
# ---------------------------------------------------------------------------
RENDER_SCALE = 4   # render at 1/RENDER_SCALE, then upscale


# ---------------------------------------------------------------------------
# Wallpaper renderers
# ---------------------------------------------------------------------------

def _wp_default_dark(w: int, h: int) -> Image.Image:
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    canvas = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(canvas)
    np = _try_numpy()
    if np is not None:
        xs = np.arange(rw)
        y_ind = (rh / 2 + rh / 5 * np.sin(xs * 0.04)).astype(int)
        y_cya = (rh / 2 + rh / 6 * np.cos(xs * 0.03 + 2.0)).astype(int)
        pixels = canvas.load()
        for x in range(rw):
            for dy in range(-28, 28):
                a = int(55 * (1.0 - abs(dy) / 28.0))
                yi = y_ind[x] + dy
                yc = y_cya[x] + dy
                if 0 <= yi < rh:
                    old = pixels[x, yi]
                    pixels[x, yi] = (
                        min(255, old[0] + _IND[0] * a // 255),
                        min(255, old[1] + _IND[1] * a // 255),
                        min(255, old[2] + _IND[2] * a // 255),
                        255,
                    )
                if 0 <= yc < rh:
                    old = pixels[x, yc]
                    pixels[x, yc] = (
                        min(255, old[0] + _CYA[0] * a // 255),
                        min(255, old[1] + _CYA[1] * a // 255),
                        min(255, old[2] + _CYA[2] * a // 255),
                        255,
                    )
    else:
        for x in range(rw):
            yi = int(rh / 2 + rh / 5 * math.sin(x * 0.04))
            yc = int(rh / 2 + rh / 6 * math.cos(x * 0.03 + 2.0))
            for dy in range(-28, 28):
                a = int(55 * (1.0 - abs(dy) / 28.0))
                if 0 <= yi + dy < rh:
                    draw.point((x, yi + dy), fill=(*_IND, a))
                if 0 <= yc + dy < rh:
                    draw.point((x, yc + dy), fill=(*_CYA, a))

    blurred = canvas.filter(ImageFilter.GaussianBlur(radius=12))
    return Image.alpha_composite(
        Image.new("RGBA", (rw, rh), (*_BG, 255)), blurred
    ).resize((w, h), Image.Resampling.LANCZOS)


def _wp_aurora(w: int, h: int) -> Image.Image:
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    canvas = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(canvas)
    bands  = [(_VIO, 0.0), (_IND, 0.33), (_CYA, 0.66)]
    for color, phase in bands:
        for x in range(rw):
            y_base = int(rh * 0.2 + rh * 0.6 * phase +
                         rh * 0.08 * math.sin(x * 0.05 + phase * 6))
            for dy in range(-40, 40):
                a = int(50 * (1.0 - abs(dy) / 40.0))
                if 0 <= y_base + dy < rh:
                    draw.point((x, y_base + dy), fill=(*color, a))
    blurred = canvas.filter(ImageFilter.GaussianBlur(radius=18))
    return Image.alpha_composite(
        Image.new("RGBA", (rw, rh), (*_BG, 255)), blurred
    ).resize((w, h), Image.Resampling.LANCZOS)


def _wp_abstract_blue(w: int, h: int) -> Image.Image:
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(base)
    np = _try_numpy()
    if np is not None:
        xs = np.linspace(0, rw - 1, rw)
        ys = np.linspace(0, rh - 1, rh)
        X, Y = np.meshgrid(xs, ys)
        V = np.sin(X * 0.06) * np.cos(Y * 0.06) + 0.5 * np.sin(X * 0.12 + Y * 0.04)
        pixels = base.load()
        for y in range(rh):
            for x in range(rw):
                v = V[y, x]
                if v > 0.3:
                    a = int(80 * (v - 0.3) / 0.7)
                    col = _CYA if v < 0.6 else _IND
                    old = pixels[x, y]
                    pixels[x, y] = (
                        min(255, old[0] + col[0] * a // 255),
                        min(255, old[1] + col[1] * a // 255),
                        min(255, old[2] + col[2] * a // 255),
                        255,
                    )
    else:
        for y in range(rh):
            for x in range(rw):
                v = math.sin(x * 0.06) * math.cos(y * 0.06)
                if v > 0.3:
                    a = int(80 * (v - 0.3))
                    draw.point((x, y), fill=(*_CYA, a))
    blurred = base.filter(ImageFilter.GaussianBlur(radius=8))
    return blurred.resize((w, h), Image.Resampling.LANCZOS)


def _wp_minimal_dark(w: int, h: int) -> Image.Image:
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(base)
    cx, cy = rw // 2, rh // 2
    for r in range(5, min(rw, rh) // 2, 8):
        a = int(30 * (1.0 - r / (min(rw, rh) / 2)))
        draw.arc([cx-r, cy-r, cx+r, cy+r], 0, 360,
                 fill=(*_IND, a), width=3)
    blurred = base.filter(ImageFilter.GaussianBlur(radius=16))
    return Image.alpha_composite(
        Image.new("RGBA", (rw, rh), (*_BG, 255)), blurred
    ).resize((w, h), Image.Resampling.LANCZOS)


def _wp_nebula(w: int, h: int) -> Image.Image:
    """Layered Perlin-like noise using sin/cos interference."""
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(base)
    np = _try_numpy()
    if np is not None:
        xs = np.linspace(0, 6.28, rw)
        ys = np.linspace(0, 6.28, rh)
        X, Y = np.meshgrid(xs, ys)
        noise = (
            np.sin(X * 1.5 + np.cos(Y * 0.8)) * 0.4 +
            np.cos(Y * 2.0 + np.sin(X * 1.2)) * 0.3 +
            np.sin((X + Y) * 0.9) * 0.3
        )
        noise = (noise - noise.min()) / (noise.max() - noise.min())
        pixels = base.load()
        colors = [_IND, _VIO, _CYA, _PRI]
        for y in range(rh):
            for x in range(rw):
                v = noise[y, x]
                ci = int(v * 3)
                ci = min(ci, 3)
                col = colors[ci]
                a = int(120 * v * (1 - abs(v - 0.5) * 2))
                old = pixels[x, y]
                pixels[x, y] = (
                    min(255, old[0] + col[0] * a // 255),
                    min(255, old[1] + col[1] * a // 255),
                    min(255, old[2] + col[2] * a // 255),
                    255,
                )
    else:
        for y in range(0, rh, 2):
            for x in range(0, rw, 2):
                v = (math.sin(x * 0.15 + math.cos(y * 0.08)) * 0.5 + 0.5)
                col = _VIO if v < 0.5 else _IND
                a = int(60 * v)
                draw.point((x, y), fill=(*col, a))
    blurred = base.filter(ImageFilter.GaussianBlur(radius=20))
    return Image.alpha_composite(
        Image.new("RGBA", (rw, rh), (*_BG, 255)), blurred
    ).resize((w, h), Image.Resampling.LANCZOS)


def _wp_circuit(w: int, h: int) -> Image.Image:
    """Procedural circuit board with traces, nodes, and vias."""
    rng   = random.Random(1337)
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(base)

    # Horizontal and vertical traces
    grid = 32
    for gx in range(0, rw, grid):
        for gy in range(0, rh, grid):
            if rng.random() > 0.45:
                # Horizontal trace
                end_x = gx + rng.randint(1, 4) * grid
                draw.line([(gx, gy), (min(end_x, rw), gy)],
                          fill=(*_IND, 60), width=1)
                # Via (circular pad)
                r = 3
                draw.ellipse([gx-r, gy-r, gx+r, gy+r], fill=(*_CYA, 80))
            if rng.random() > 0.55:
                end_y = gy + rng.randint(1, 3) * grid
                draw.line([(gx, gy), (gx, min(end_y, rh))],
                          fill=(*_IND, 45), width=1)
            # Component pads
            if rng.random() > 0.85:
                pw, ph = rng.randint(8, 20), rng.randint(4, 10)
                draw.rectangle([gx, gy, gx+pw, gy+ph],
                               outline=(*_CYA, 50), width=1)

    blurred = base.filter(ImageFilter.GaussianBlur(radius=2))
    return blurred.resize((w, h), Image.Resampling.LANCZOS)


def _wp_geometric(w: int, h: int) -> Image.Image:
    """Tiled hexagonal grid with gradient fill per cell."""
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    draw   = ImageDraw.Draw(base)

    hex_r = 30  # hex radius
    hex_h = int(hex_r * math.sqrt(3))
    hex_w = hex_r * 2

    def hex_corners(cx, cy, r):
        return [
            (cx + r * math.cos(math.radians(60 * i - 30)),
             cy + r * math.sin(math.radians(60 * i - 30)))
            for i in range(6)
        ]

    row_idx = 0
    for gy in range(-hex_r, rh + hex_r, hex_h):
        for gx in range(-hex_r, rw + hex_r, int(hex_w * 1.5)):
            cx = gx + (hex_r if row_idx % 2 else 0)
            cy = gy
            t  = ((cx / rw) + (cy / rh)) / 2.0
            col = (
                int(_IND[0] * (1-t) + _CYA[0] * t),
                int(_IND[1] * (1-t) + _CYA[1] * t),
                int(_IND[2] * (1-t) + _CYA[2] * t),
            )
            corners = hex_corners(cx, cy, hex_r - 2)
            draw.polygon(corners, outline=(*col, 40), fill=(*col, 12))
        row_idx += 1

    blurred = base.filter(ImageFilter.GaussianBlur(radius=4))
    return blurred.resize((w, h), Image.Resampling.LANCZOS)


def _wp_deep_space(w: int, h: int) -> Image.Image:
    """Star field with Gaussian blur halos + nebula clouds."""
    rng    = random.Random(2048)
    rw, rh = w // RENDER_SCALE, h // RENDER_SCALE
    base   = Image.new("RGBA", (rw, rh), (*_BG, 255))
    stars  = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    sdraw  = ImageDraw.Draw(stars)

    # Stars
    for _ in range(600):
        sx = rng.randint(0, rw - 1)
        sy = rng.randint(0, rh - 1)
        sr = rng.randint(1, 3)
        sa = rng.randint(120, 255)
        col = rng.choice([(255, 255, 255), _CYA, _IND, (255, 255, 220)])
        sdraw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill=(*col[:3], sa))

    # Big bright stars with halo
    for _ in range(20):
        sx = rng.randint(0, rw-1)
        sy = rng.randint(0, rh-1)
        for hr in range(12, 0, -2):
            ha = int(80 * (1 - hr / 12.0))
            sdraw.ellipse([sx-hr, sy-hr, sx+hr, sy+hr], fill=(255, 255, 255, ha))
        sdraw.ellipse([sx-2, sy-2, sx+2, sy+2], fill=(255, 255, 255, 255))

    # Nebula blobs
    nebula = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    ndraw  = ImageDraw.Draw(nebula)
    for _ in range(8):
        nx = rng.randint(0, rw)
        ny = rng.randint(0, rh)
        nr = rng.randint(40, 120)
        col = rng.choice([_IND, _VIO, _CYA])
        for nr2 in range(nr, 0, -10):
            na = int(30 * (1 - nr2 / nr))
            ndraw.ellipse([nx-nr2, ny-nr2, nx+nr2, ny+nr2], fill=(*col, na))

    nebula_blurred = nebula.filter(ImageFilter.GaussianBlur(radius=20))
    stars_blurred  = stars.filter(ImageFilter.GaussianBlur(radius=1))

    result = Image.alpha_composite(base, nebula_blurred)
    result = Image.alpha_composite(result, stars_blurred)
    return result.resize((w, h), Image.Resampling.LANCZOS)


_WP_RENDERERS = {
    "default_dark":  _wp_default_dark,
    "aurora":        _wp_aurora,
    "abstract_blue": _wp_abstract_blue,
    "minimal_dark":  _wp_minimal_dark,
    "nebula":        _wp_nebula,
    "circuit":       _wp_circuit,
    "geometric":     _wp_geometric,
    "deep_space":    _wp_deep_space,
}


def generate_all_wallpapers(target_root: str) -> None:
    wallpapers_dir = ensure_dir(os.path.join(target_root, "wallpapers"))
    total = len(WALLPAPER_TYPES) * len(WALLPAPER_RESOLUTIONS)

    with ProgressReporter(total, desc="Wallpapers") as prog:
        for wp_type in WALLPAPER_TYPES:
            renderer = _WP_RENDERERS.get(wp_type)
            if renderer is None:
                logger.warning(f"No renderer for wallpaper type: {wp_type}")
                prog.advance(len(WALLPAPER_RESOLUTIONS))
                continue

            type_dir = ensure_dir(os.path.join(wallpapers_dir, wp_type))
            for (res_w, res_h, label) in WALLPAPER_RESOLUTIONS:
                out_path = os.path.join(type_dir, f"{wp_type}_{label}.png")
                img = renderer(res_w, res_h)
                img.convert("RGB").save(out_path, "PNG", optimize=False)
                prog.advance(1, postfix=f"{wp_type}@{label}")

    logger.info(
        f"Wallpapers: generated {len(WALLPAPER_TYPES)} types "
        f"× {len(WALLPAPER_RESOLUTIONS)} resolutions"
    )
