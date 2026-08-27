"""
branding_generator/animations.py
Full animation pipeline for PyFlare.

Outputs per animation type:
  - PNG frame sequence  (animations/{cat}/frames/frame_NN.png)
  - Animated WebP       (animations/{cat}.webp)
  - Animated GIF        (animations/{cat}.gif)
  - Lottie JSON         (animations/{cat}.json)
  - MP4 preview         (animations/{cat}.mp4) — requires imageio[ffmpeg]

Animations use proper easing curves and unique per-type visuals.
"""

import os
import math
import json
import logging
from PIL import Image, ImageDraw, ImageFilter

from branding_generator.config import BRAND_COLORS, ANIMATION_CONFIGS
from branding_generator.utils import (
    ensure_dir, ProgressReporter,
    ease_in_out_cubic, ease_out_elastic, ease_in_expo, ease_out_cubic, linear,
    get_easing_fn, hex_to_rgb, rgb_lerp,
)

logger = logging.getLogger("pyflare-brand")

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
_IND = hex_to_rgb(BRAND_COLORS["indigo"])
_CYA = hex_to_rgb(BRAND_COLORS["cyan"])
_VIO = hex_to_rgb(BRAND_COLORS["violet"])
_BG  = hex_to_rgb(BRAND_COLORS["background"])
_GRN = (16, 185, 129)   # success green
_RED = (239, 68,  68)   # error red


# ---------------------------------------------------------------------------
# Frame renderers — each returns a list of RGBA PIL Images
# ---------------------------------------------------------------------------

def _render_boot_frames(n: int, size: int) -> list:
    """PyFlare logo assembling from 3 fragment pieces with glow trails."""
    frames = []
    cx = cy = size // 2
    for i in range(n):
        t  = ease_in_out_cubic(i / (n - 1))
        img = Image.new("RGBA", (size, size), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Animated glow background
        glow_r = int(size * 0.15 + size * 0.2 * t)
        glow_a = int(60 * t)
        for gr in range(glow_r, 0, -8):
            a = int(glow_a * (1 - gr / glow_r))
            draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*_IND, a))

        # 3 flame petals flying in from different angles
        fragment_offsets = [
            (0,  -size * (1 - t) * 0.8),   # top petal descends
            (-size * (1-t) * 0.6, size * (1-t) * 0.5),  # left petal
            ( size * (1-t) * 0.6, size * (1-t) * 0.5),  # right petal
        ]
        petal_colors = [(*_IND, int(200 * t)), (*_VIO, int(200 * t)), (*_CYA, int(200 * t))]

        for (ox, oy), color in zip(fragment_offsets, petal_colors):
            r = int(size * 0.22)
            ex = cx + int(ox)
            ey = cy + int(oy)
            draw.ellipse([ex - r, ey - r*2, ex + r, ey + r], fill=color)

        # Glow streak trails
        if t > 0.2:
            trail_a = int(120 * (1 - t))
            for jr in range(1, 5):
                draw.ellipse(
                    [cx - jr*3, cy - jr*3, cx + jr*3, cy + jr*3],
                    fill=(*_CYA, trail_a // jr),
                )

        frames.append(img.filter(ImageFilter.GaussianBlur(radius=1 if t < 0.9 else 0)))
    return frames


def _render_shutdown_frames(n: int, size: int) -> list:
    """Logo dissolving outward with fading particle trails."""
    frames = []
    cx = cy = size // 2
    for i in range(n):
        t   = ease_in_expo(i / (n - 1))
        img = Image.new("RGBA", (size, size), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        alpha = int(255 * (1 - t))
        scale = 1.0 + t * 0.5

        # Expanding logo silhouette
        r = int(size * 0.25 * scale)
        draw.ellipse([cx - r, cy - r*2, cx + r, cy + r], fill=(*_IND, alpha))
        draw.ellipse([cx - r//2, cy - r, cx + r//2, cy + r//2], fill=(*_CYA, alpha))

        # Dissolving particles
        import random
        rng = random.Random(i * 42)
        for _ in range(16):
            angle = rng.uniform(0, 2*math.pi)
            dist  = rng.uniform(size * 0.15, size * 0.45) * t
            px    = cx + int(dist * math.cos(angle))
            py    = cy + int(dist * math.sin(angle))
            pr    = rng.randint(2, 6)
            pa    = int((1-t) * rng.randint(100, 200))
            color = _IND if rng.random() > 0.5 else _CYA
            draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=(*color, pa))

        frames.append(img)
    return frames


def _render_loading_frames(n: int, size: int) -> list:
    """Orbiting dots with comet tails and alpha fade (loops)."""
    frames = []
    cx = cy = size // 2
    for i in range(n):
        t    = i / n
        img  = Image.new("RGBA", (size, size), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Outer track ring (dim)
        r_track = size * 36 // 100
        draw.arc([cx - r_track, cy - r_track, cx + r_track, cy + r_track],
                 0, 360, fill=(*_IND, 30), width=max(2, size//20))

        # Center logo pulse
        pulse = 0.85 + 0.15 * math.sin(t * 2 * math.pi)
        r_c   = int(size * 0.10 * pulse)
        draw.ellipse([cx - r_c, cy - r_c, cx + r_c, cy + r_c], fill=(*_CYA, 180))

        # 4 orbiting dots with comet tails
        n_dots = 4
        for d in range(n_dots):
            dot_t  = (t + d / n_dots) % 1.0
            angle  = dot_t * 2 * math.pi - math.pi / 2
            dx     = cx + int(r_track * math.cos(angle))
            dy_    = cy + int(r_track * math.sin(angle))
            # Dot
            r_dot  = max(2, size // 16)
            alpha  = int(200 + 55 * math.sin(dot_t * 2 * math.pi))
            color  = rgb_lerp(_CYA, _IND, d / n_dots)
            draw.ellipse([dx-r_dot, dy_-r_dot, dx+r_dot, dy_+r_dot], fill=(*color, alpha))
            # Comet tail (8 previous positions)
            for tail_i in range(1, 9):
                tail_frac = tail_i / 9.0
                tail_t    = (dot_t - tail_frac * 0.12) % 1.0
                tail_ang  = tail_t * 2 * math.pi - math.pi / 2
                tx = cx + int(r_track * math.cos(tail_ang))
                ty = cy + int(r_track * math.sin(tail_ang))
                tr = max(1, r_dot - tail_i // 2)
                ta = int(alpha * (1 - tail_frac) * 0.5)
                draw.ellipse([tx-tr, ty-tr, tx+tr, ty+tr], fill=(*color, ta))

        frames.append(img)
    return frames


def _render_success_frames(n: int, size: int) -> list:
    """Checkmark drawing itself with green particle burst."""
    frames = []
    cx = cy = size // 2
    # Check path: (x1,y1) → (x2,y2) → (x3,y3)
    p1 = (size * 18//100, size * 50//100)
    p2 = (size * 42//100, size * 72//100)
    p3 = (size * 80//100, size * 28//100)

    for i in range(n):
        t   = ease_out_cubic(i / (n - 1))
        img = Image.new("RGBA", (size, size), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Background ring
        r_ring = size * 36 // 100
        a_ring = int(80 + 120 * t)
        draw.arc([cx - r_ring, cy - r_ring, cx + r_ring, cy + r_ring],
                 0, 360, fill=(*_GRN, a_ring), width=max(2, size//16))

        # Checkmark drawing progress
        check_len = t
        w = max(2, size // 14)
        if check_len > 0:
            # First segment: p1 → p2
            seg1_frac = min(check_len / 0.45, 1.0)
            mid_x = int(p1[0] + (p2[0] - p1[0]) * seg1_frac)
            mid_y = int(p1[1] + (p2[1] - p1[1]) * seg1_frac)
            draw.line([p1, (mid_x, mid_y)], fill=(*_GRN, 255), width=w)
            if check_len > 0.45:
                # Second segment: p2 → p3
                seg2_frac = min((check_len - 0.45) / 0.55, 1.0)
                end_x = int(p2[0] + (p3[0] - p2[0]) * seg2_frac)
                end_y = int(p2[1] + (p3[1] - p2[1]) * seg2_frac)
                draw.line([p2, (end_x, end_y)], fill=(*_GRN, 255), width=w)

        # Particle burst
        if t > 0.7:
            import random
            rng = random.Random(42)
            burst_t = (t - 0.7) / 0.3
            for _ in range(20):
                angle = rng.uniform(0, 2*math.pi)
                dist  = rng.uniform(size*0.2, size*0.46) * burst_t
                px    = cx + int(dist * math.cos(angle))
                py    = cy + int(dist * math.sin(angle))
                pr    = rng.randint(2, 5)
                pa    = int((1 - burst_t) * 200)
                draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=(*_GRN, pa))

        frames.append(img)
    return frames


def _render_error_frames(n: int, size: int) -> list:
    """X mark drawing itself with red shockwave."""
    frames = []
    cx = cy = size // 2
    r = size * 28 // 100

    for i in range(n):
        t   = ease_in_out_cubic(i / (n - 1))
        img = Image.new("RGBA", (size, size), (*_BG, 255))
        draw = ImageDraw.Draw(img)

        # Shockwave rings
        for ring_i in range(1, 4):
            ring_t = (t - (ring_i - 1) * 0.2)
            if ring_t > 0:
                ring_t = min(ring_t / 0.5, 1.0)
                ring_r = int(size * 0.12 + size * 0.38 * ring_t)
                ring_a = int(160 * (1 - ring_t))
                draw.arc([cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r],
                         0, 360, fill=(*_RED, ring_a), width=max(1, size//22))

        # X mark progress
        w = max(2, size // 14)
        if t > 0:
            frac = min(t / 0.6, 1.0)
            # First stroke: top-left → bottom-right
            ex1 = int((cx - r) + (cx + r - (cx - r)) * frac)
            ey1 = int((cy - r) + (cy + r - (cy - r)) * frac)
            draw.line([(cx - r, cy - r), (ex1, ey1)], fill=(*_RED, 255), width=w)
            if t > 0.4:
                frac2 = min((t - 0.4) / 0.6, 1.0)
                ex2 = int((cx + r) + (cx - r - (cx + r)) * frac2)
                ey2 = int((cy - r) + (cy + r - (cy - r)) * frac2)
                draw.line([(cx + r, cy - r), (ex2, ey2)], fill=(*_RED, 255), width=w)

        frames.append(img)
    return frames


_FRAME_RENDERERS = {
    "boot":     _render_boot_frames,
    "shutdown": _render_shutdown_frames,
    "loading":  _render_loading_frames,
    "success":  _render_success_frames,
    "error":    _render_error_frames,
}


# ---------------------------------------------------------------------------
# Output format writers
# ---------------------------------------------------------------------------

def _write_webp(frames: list, path: str, fps: int, loop: bool):
    duration_ms = max(1, 1000 // fps)
    frames[0].save(
        path, format="WEBP", save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0 if loop else 1,
    )


def _write_gif(frames: list, path: str, fps: int, loop: bool):
    duration_ms = max(20, 1000 // fps)
    gif_frames = [f.convert("RGBA") for f in frames]
    gif_frames[0].save(
        path, format="GIF", save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=0 if loop else 1,
        disposal=2,
    )


def _write_mp4(frames: list, path: str, fps: int) -> bool:
    try:
        import imageio
        import numpy as np
        writer = imageio.get_writer(path, fps=fps, codec="libx264",
                                    pixelformat="yuv420p", quality=8)
        for frame in frames:
            arr = np.array(frame.convert("RGB"))
            writer.append_data(arr)
        writer.close()
        return True
    except ImportError:
        logger.info("imageio[ffmpeg] not installed — skipping MP4 export")
        return False
    except Exception as e:
        logger.warning(f"MP4 export failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Lottie JSON builder
# ---------------------------------------------------------------------------

def _lottie_ease_handle(easing_name: str) -> dict:
    """Return Lottie bezier handle for common easing types."""
    _handles = {
        "ease_in_out_cubic": {"i": {"x": [0.42], "y": [0]},   "o": {"x": [0.58], "y": [1]}},
        "ease_out_elastic":  {"i": {"x": [0.0],  "y": [1.5]}, "o": {"x": [0.58], "y": [1]}},
        "ease_in_expo":      {"i": {"x": [0.95], "y": [0.05]},"o": {"x": [1.0],  "y": [0.0]}},
        "linear":            {"i": {"x": [0.5],  "y": [0.5]}, "o": {"x": [0.5],  "y": [0.5]}},
    }
    return _handles.get(easing_name, _handles["ease_in_out_cubic"])


def _build_lottie(name: str, cfg: dict) -> dict:
    """Build a minimal but valid Lottie 5.x JSON structure."""
    n_frames = cfg["frame_count"]
    fps      = cfg["fps"]
    size     = cfg["size"]
    easing   = cfg["easing"]
    loop_val = 1 if cfg.get("loop") else 0
    ease_h   = _lottie_ease_handle(easing)

    # Rotation keyframes: 0° → 360° for loading, else logo scale pulse
    if name == "loading":
        kf_prop = {
            "a": 1,
            "k": [
                {**ease_h, "t": 0,         "s": [0]},
                {**ease_h, "t": n_frames,  "s": [360]},
            ],
        }
        shape_layer = {
            "ty": "sh", "nm": "Spinner",
            "ks": {"r": kf_prop},
            "shapes": [
                {
                    "ty": "el",
                    "s": {"a": 0, "k": [size * 0.7, size * 0.7]},
                    "p": {"a": 0, "k": [size / 2, size / 2]},
                },
                {
                    "ty": "st",
                    "c": {"a": 0, "k": [0, 0.83, 1, 1]},
                    "w": {"a": 0, "k": size * 0.06},
                    "lc": 2, "lj": 2,
                    "d": [{"n": "o", "nm": "dash", "v": {"a": 0, "k": size * 0.8}}],
                },
            ],
        }
    else:
        scale_kf = {
            "a": 1,
            "k": [
                {**ease_h, "t": 0,          "s": [0, 0]},
                {**ease_h, "t": n_frames//2, "s": [110, 110]},
                {**ease_h, "t": n_frames,    "s": [100, 100]},
            ],
        }
        opacity_kf = {
            "a": 1,
            "k": [
                {**ease_h, "t": 0,         "s": [0]},
                {**ease_h, "t": n_frames//3,"s": [100]},
                {**ease_h, "t": n_frames,   "s": [100]},
            ],
        }
        shape_layer = {
            "ty": "sh", "nm": f"{name} logo",
            "ks": {
                "s": scale_kf,
                "o": opacity_kf,
                "p": {"a": 0, "k": [size / 2, size / 2]},
            },
            "shapes": [
                {
                    "ty": "el",
                    "s": {"a": 0, "k": [size * 0.5, size * 0.5]},
                    "p": {"a": 0, "k": [0, 0]},
                },
                {
                    "ty": "fl",
                    "c": {"a": 0, "k": [0.36, 0.37, 1, 1]},  # indigo
                    "o": {"a": 0, "k": 100},
                },
            ],
        }

    return {
        "v":  "5.9.4",
        "fr": fps,
        "ip": 0,
        "op": n_frames,
        "w":  size,
        "h":  size,
        "nm": f"PyFlare {name.capitalize()} Animation",
        "ddd": 0,
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty":  4,
                "nm":  f"{name}",
                "sr":  1,
                "ks":  shape_layer.get("ks", {}),
                "ao":  0,
                "ip":  0,
                "op":  n_frames,
                "st":  0,
                "bm":  0,
                "shapes": shape_layer.get("shapes", []),
            }
        ],
        "m
# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_all_animations(target_root: str) -> None:
    anim_root = ensure_dir(os.path.join(target_root, "animations"))

    total_categories = len(ANIMATION_CONFIGS)
    with ProgressReporter(total_categories, desc="Animations") as prog:
        for cat, cfg in ANIMATION_CONFIGS.items():
            n    = cfg["frame_count"]
            size = cfg["size"]
            fps  = cfg["fps"]
            loop = cfg.get("loop", False)

            # Render frames in memory only — no PNG dumps
            renderer = _FRAME_RENDERERS.get(cat, _render_loading_frames)
            frames   = renderer(n, size)

            # 1. Animated WebP  → animations/{cat}.webp
            _write_webp(frames, os.path.join(anim_root, f"{cat}.webp"), fps, loop)

            # 2. Animated GIF   → animations/{cat}.gif
            _write_gif(frames, os.path.join(anim_root, f"{cat}.gif"), fps, loop)

            # 3. MP4 preview    → animations/{cat}.mp4  (skipped silently if no ffmpeg)
            _write_mp4(frames, os.path.join(anim_root, f"{cat}.mp4"), fps)

            # 4. Lottie JSON    → animations/{cat}.json
            lottie_data = _build_lottie(cat, cfg)
            with open(os.path.join(anim_root, f"{cat}.json"), "w") as jf:
                json.dump(lottie_data, jf, indent=2)

            prog.advance(1, postfix=cat)

    logger.info(
        f"Animations: {total_categories} types → WebP + GIF + MP4 + Lottie JSON "
        f"in animations/"
    )
Lottie JSON)"
    )
