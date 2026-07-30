"""
branding_generator/utils.py
Shared helper utilities: logging, filesystem, colour conversion,
math/SDF, easing, gradient rendering, glow composition,
incremental build cache, and progress reporting.
"""

import os
import math
import json
import hashlib
import logging
import subprocess
from typing import Tuple, List, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logger(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("pyflare-brand")


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str) -> str:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    os.makedirs(path, exist_ok=True)
    return path


def file_sha256(path: str) -> str:
    """Return hex SHA-256 digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Incremental build cache
# ---------------------------------------------------------------------------

class BuildCache:
    """
    Persist a {output_path: source_hash} mapping so incremental builds
    can skip regenerating unchanged assets.
    """

    def __init__(self, cache_file: str):
        self._path = cache_file
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def is_fresh(self, output_path: str, source_hash: str) -> bool:
        return self._data.get(output_path) == source_hash

    def mark(self, output_path: str, source_hash: str):
        self._data[output_path] = source_hash


# ---------------------------------------------------------------------------
# Progress reporting  (tqdm if available, else plain counter)
# ---------------------------------------------------------------------------

class ProgressReporter:
    def __init__(self, total: int, desc: str = ""):
        self._n = 0
        self._total = total
        self._desc = desc
        try:
            from tqdm import tqdm
            self._bar = tqdm(total=total, desc=desc, unit="asset",
                             bar_format="{l_bar}{bar:30}{r_bar}")
            self._use_tqdm = True
        except ImportError:
            self._bar = None
            self._use_tqdm = False
            logger = logging.getLogger("pyflare-brand")
            logger.info(f"[{desc}] 0/{total}")

    def advance(self, n: int = 1, postfix: str = ""):
        self._n += n
        if self._use_tqdm and self._bar:
            if postfix:
                self._bar.set_postfix_str(postfix)
            self._bar.update(n)
        else:
            logger = logging.getLogger("pyflare-brand")
            logger.debug(f"[{self._desc}] {self._n}/{self._total} {postfix}")

    def close(self):
        if self._use_tqdm and self._bar:
            self._bar.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ---------------------------------------------------------------------------
# Colour conversion
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """'#RRGGBB' → (R, G, B)"""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


def hex_to_rgba(hex_str: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(hex_str)
    return r, g, b, alpha


def rgb_lerp(
    c0: Tuple[int, int, int],
    c1: Tuple[int, int, int],
    t: float,
) -> Tuple[int, int, int]:
    """Linear interpolate between two RGB tuples."""
    return (
        int(c0[0] + (c1[0] - c0[0]) * t),
        int(c0[1] + (c1[1] - c0[1]) * t),
        int(c0[2] + (c1[2] - c0[2]) * t),
    )


# ---------------------------------------------------------------------------
# Easing functions  (t ∈ [0, 1] → [0, 1])
# ---------------------------------------------------------------------------

def linear(t: float) -> float:
    return t


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    p = 2 * t - 2
    return 1 + 0.5 * p * p * p


def ease_out_elastic(t: float) -> float:
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def ease_in_expo(t: float) -> float:
    return 0.0 if t == 0 else pow(2, 10 * t - 10)


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def get_easing_fn(name: str):
    _map = {
        "linear":           linear,
        "ease_in_out_cubic": ease_in_out_cubic,
        "ease_out_elastic": ease_out_elastic,
        "ease_in_expo":     ease_in_expo,
        "ease_out_cubic":   ease_out_cubic,
    }
    return _map.get(name, linear)


# ---------------------------------------------------------------------------
# SDF (Signed Distance Field) primitives — float pixel space
# ---------------------------------------------------------------------------

def sdf_circle(x: float, y: float, cx: float, cy: float, r: float) -> float:
    return math.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r


def sdf_box(
    x: float, y: float,
    cx: float, cy: float,
    w: float, h: float,
) -> float:
    dx = abs(x - cx) - w / 2
    dy = abs(y - cy) - h / 2
    return math.sqrt(max(dx, 0) ** 2 + max(dy, 0) ** 2) + min(max(dx, dy), 0.0)


def sdf_rounded_box(
    x: float, y: float,
    cx: float, cy: float,
    w: float, h: float,
    r: float,
) -> float:
    dx = abs(x - cx) - (w / 2 - r)
    dy = abs(y - cy) - (h / 2 - r)
    return math.sqrt(max(dx, 0) ** 2 + max(dy, 0) ** 2) + min(max(dx, dy), 0.0) - r


# ---------------------------------------------------------------------------
# PIL gradient builders (require Pillow — always available in this project)
# ---------------------------------------------------------------------------

def build_linear_gradient_pixels(
    width: int, height: int,
    color_start: Tuple[int, int, int],
    color_end:   Tuple[int, int, int],
    angle_deg: float = 135,
) -> "Image.Image":
    """Return an RGBA PIL Image filled with a linear gradient."""
    from PIL import Image
    img = Image.new("RGBA", (width, height))
    pixels = img.load()
    rad = math.radians(angle_deg)
    dx = math.cos(rad)
    dy = math.sin(rad)
    # Project corner to find min/max dot products
    corners = [(0, 0), (width, 0), (0, height), (width, height)]
    dots = [x * dx + y * dy for x, y in corners]
    d_min, d_max = min(dots), max(dots)
    d_range = d_max - d_min or 1.0
    for y in range(height):
        for x in range(width):
            t = (x * dx + y * dy - d_min) / d_range
            r, g, b = rgb_lerp(color_start, color_end, t)
            pixels[x, y] = (r, g, b, 255)
    return img


def build_radial_gradient_pixels(
    width: int, height: int,
    color_inner: Tuple[int, int, int],
    color_outer: Tuple[int, int, int],
    cx: Optional[float] = None,
    cy: Optional[float] = None,
) -> "Image.Image":
    """Return an RGBA PIL Image with a radial gradient."""
    from PIL import Image
    img = Image.new("RGBA", (width, height))
    pixels = img.load()
    if cx is None:
        cx = width / 2
    if cy is None:
        cy = height / 2
    max_r = math.sqrt(cx ** 2 + cy ** 2)
    for y in range(height):
        for x in range(width):
            d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            t = min(d / max_r, 1.0)
            r, g, b = rgb_lerp(color_inner, color_outer, t)
            pixels[x, y] = (r, g, b, 255)
    return img


def apply_glow(
    base: "Image.Image",
    overlay_color: Tuple[int, int, int],
    radius: int = 40,
    intensity: float = 0.5,
) -> "Image.Image":
    """
    Composite a soft radial glow layer over a base image.
    Returns a new RGBA image.
    """
    from PIL import Image, ImageFilter
    w, h = base.size
    glow = build_radial_gradient_pixels(
        w, h,
        (int(overlay_color[0] * intensity),
         int(overlay_color[1] * intensity),
         int(overlay_color[2] * intensity)),
        (0, 0, 0),
    )
    glow_blurred = glow.filter(ImageFilter.GaussianBlur(radius=radius))
    result = Image.alpha_composite(base.convert("RGBA"), glow_blurred.convert("RGBA"))
    return result


# ---------------------------------------------------------------------------
# Optional external tool runner
# ---------------------------------------------------------------------------

def run_subprocess_safe(cmd: List[str], fallback_msg: str = "") -> bool:
    """
    Run an external command. Returns True on success, False on failure/not-found.
    Never raises an exception.
    """
    _log = logging.getLogger("pyflare-brand")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True
        _log.warning(
            f"Command {cmd[0]} failed (rc={result.returncode}): "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
        return False
    except FileNotFoundError:
        if fallback_msg:
            _log.info(f"{cmd[0]} not found — {fallback_msg}")
        return False
    except Exception as e:
        _log.warning(f"Subprocess error running {cmd}: {e}")
        return False


# ---------------------------------------------------------------------------
# SVG defs block builder (helpers for icons.py)
# ---------------------------------------------------------------------------

def svg_linear_gradient(
    gid: str,
    stops: List[Tuple[str, str]],  # [(offset, color), ...]
    x1="0%", y1="0%", x2="100%", y2="100%",
) -> str:
    stop_tags = "".join(
        f'    <stop offset="{o}" stop-color="{c}"/>\n'
        for o, c in stops
    )
    return (
        f'  <linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'gradientUnits="objectBoundingBox">\n{stop_tags}  </linearGradient>\n'
    )


def svg_radial_gradient(
    gid: str,
    stops: List[Tuple[str, str]],
    cx="50%", cy="50%", r="50%",
) -> str:
    stop_tags = "".join(
        f'    <stop offset="{o}" stop-color="{c}"/>\n'
        for o, c in stops
    )
    return (
        f'  <radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}" '
        f'gradientUnits="objectBoundingBox">\n{stop_tags}  </radialGradient>\n'
    )


def svg_drop_shadow_filter(
    fid: str,
    dx: float = 0, dy: float = 4,
    stddev: float = 8,
    color: str = "#000000",
    opacity: float = 0.5,
) -> str:
    return (
        f'  <filter id="{fid}" x="-20%" y="-20%" width="140%" height="140%">\n'
        f'    <feDropShadow dx="{dx}" dy="{dy}" stdDeviation="{stddev}" '
        f'flood-color="{color}" flood-opacity="{opacity}"/>\n'
        f'  </filter>\n'
    )


def svg_glow_filter(fid: str, color: str = "#5B5FFF", stddev: float = 12) -> str:
    return (
        f'  <filter id="{fid}" x="-30%" y="-30%" width="160%" height="160%">\n'
        f'    <feGaussianBlur stdDeviation="{stddev}" result="blur"/>\n'
        f'    <feFlood flood-color="{color}" flood-opacity="0.6" result="color"/>\n'
        f'    <feComposite in="color" in2="blur" operator="in" result="glow"/>\n'
        f'    <feMerge><feMergeNode in="glow"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
        f'  </filter>\n'
    )
