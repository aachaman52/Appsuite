"""
branding_generator/cursors.py
Full cursor generation pipeline for Linux (XCursor), Windows (.cur),
and macOS (PNG exports).

Linux XCursor binary format is written in pure Python (no xcursorgen
dependency) so the generator works on all platforms.  If xcursorgen is
found on the PATH it is also invoked as a secondary check.

All cursor PNGs are drawn in PIL using the PyFlare colour palette with
proper anti-aliased edges and per-cursor hotspot metadata.
"""

import os
import io
import math
import struct
import logging
import json
from PIL import Image, ImageDraw, ImageFilter

from branding_generator.config import BRAND_COLORS, CURSOR_DEFINITIONS, XCURSOR_SIZES
from branding_generator.utils import ensure_dir, ProgressReporter, run_subprocess_safe

logger = logging.getLogger("pyflare-brand")

# Colour aliases
_IND = tuple(int(BRAND_COLORS["indigo"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
_CYA = tuple(int(BRAND_COLORS["cyan"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
_BG  = tuple(int(BRAND_COLORS["background"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
_WHT = (255, 255, 255)
_BLK = (0,   0,   0)

RENDER_SIZE = 48  # base cursor canvas size in pixels


# ---------------------------------------------------------------------------
# Cursor artwork drawers
# ---------------------------------------------------------------------------

def _draw_default(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Left-pointing arrow with drop shadow."""
    tip = (s * 4 // 48, s * 4 // 48)
    pts = [
        tip,
        (s * 4 // 48, s * 38 // 48),
        (s * 16 // 48, s * 28 // 48),
        (s * 26 // 48, s * 44 // 48),
        (s * 32 // 48, s * 40 // 48),
        (s * 22 // 48, s * 25 // 48),
        (s * 34 // 48, s * 20 // 48),
    ]
    # shadow
    shadow = [(x+1, y+2) for x, y in pts]
    draw.polygon(shadow, fill=(*_BLK, 80))
    # fill
    draw.polygon(pts, fill=(*_CYA, 255))
    # outline
    draw.line(pts + [pts[0]], fill=(*_IND, 255), width=max(1, s // 24))


def _draw_pointer(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Hand with pointing index finger."""
    w = s // 12
    # Palm
    draw.rounded_rectangle([s*14//48, s*22//48, s*38//48, s*44//48],
                             radius=s//8, fill=(*_CYA, 240), outline=(*_IND, 255), width=w)
    # Index finger
    draw.rounded_rectangle([s*20//48, s*6//48,  s*28//48, s*28//48],
                             radius=s//10, fill=(*_CYA, 240), outline=(*_IND, 255), width=w)
    # Middle finger (slightly lower)
    draw.rounded_rectangle([s*28//48, s*10//48, s*36//48, s*26//48],
                             radius=s//10, fill=(*_CYA, 200), outline=(*_IND, 255), width=w)
    # Ring finger (lower still)
    draw.rounded_rectangle([s*34//48, s*14//48, s*42//48, s*26//48],
                             radius=s//10, fill=(*_CYA, 160), outline=(*_IND, 200), width=w)


def _draw_hand(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Open hand silhouette."""
    w = max(1, s // 24)
    cx, cy = s // 2, s * 30 // 48
    # Palm
    draw.ellipse([cx - s*14//48, cy - s*12//48, cx + s*14//48, cy + s*14//48],
                 fill=(*_CYA, 230), outline=(*_IND, 255), width=w)
    # Five fingers
    finger_bases = [-s*11//48, -s*5//48, s*1//48, s*7//48, s*13//48]
    heights       = [s*22//48, s*18//48, s*16//48, s*18//48, s*22//48]
    for bx, ht in zip(finger_bases, heights):
        draw.rounded_rectangle(
            [cx + bx, cy - ht, cx + bx + s*4//48, cy - s*6//48],
            radius=s//12, fill=(*_CYA, 220), outline=(*_IND, 255), width=w,
        )


def _draw_text(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """I-beam cursor."""
    w  = max(1, s // 20)
    cx = s // 2
    # Vertical bar
    draw.line([(cx, s*4//48), (cx, s*44//48)], fill=(*_CYA, 255), width=w*2)
    # Top serif
    draw.line([(cx - s*7//48, s*4//48), (cx + s*7//48, s*4//48)], fill=(*_CYA, 255), width=w*2)
    # Bottom serif
    draw.line([(cx - s*7//48, s*44//48), (cx + s*7//48, s*44//48)], fill=(*_CYA, 255), width=w*2)
    # Outline
    draw.line([(cx, s*4//48), (cx, s*44//48)], fill=(*_IND, 255), width=w)


def _draw_busy(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Circular arc spinner (single frame)."""
    r    = s * 18 // 48
    cx   = s // 2
    cy   = s // 2
    bbox = [cx - r, cy - r, cx + r, cy + r]
    w    = max(2, s // 10)
    # Track ring
    draw.arc(bbox, 0, 360, fill=(*_IND, 60), width=w)
    # Active arc (top-right quarter, cyan)
    draw.arc(bbox, -90, 45, fill=(*_CYA, 255), width=w)
    # Center dot
    draw.ellipse([cx - s*3//48, cy - s*3//48, cx + s*3//48, cy + s*3//48],
                 fill=(*_CYA, 200))


def _draw_working(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Arrow + busy spinner combo."""
    tip = (s * 4 // 48, s * 4 // 48)
    pts = [
        tip,
        (s * 4 // 48, s * 28 // 48),
        (s * 14 // 48, s * 20 // 48),
        (s * 24 // 48, s * 34 // 48),
        (s * 30 // 48, s * 30 // 48),
        (s * 20 // 48, s * 16 // 48),
        (s * 28 // 48, s * 12 // 48),
    ]
    draw.polygon(pts, fill=(*_CYA, 230))
    draw.line(pts + [pts[0]], fill=(*_IND, 255), width=max(1, s // 26))
    # Small spinner badge
    cx, cy = s * 36 // 48, s * 36 // 48
    r      = s * 9 // 48
    bbox   = [cx-r, cy-r, cx+r, cy+r]
    w      = max(1, s // 14)
    draw.arc(bbox, 0, 360, fill=(*_IND, 80), width=w)
    draw.arc(bbox, -90, 60, fill=(*_CYA, 255), width=w)


def _draw_move(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """4-directional move arrows."""
    cx, cy = s // 2, s // 2
    a      = s * 14 // 48  # arm length
    aw     = max(1, s // 14)  # shaft width
    ah     = s * 5 // 48   # arrowhead half-width

    def _arrow(dx, dy):
        # shaft
        draw.line([(cx, cy), (cx + dx*a, cy + dy*a)], fill=(*_CYA, 255), width=aw)
        # arrowhead
        if dx != 0:
            draw.polygon([
                (cx + dx*(a + ah), cy),
                (cx + dx*a, cy - ah),
                (cx + dx*a, cy + ah),
            ], fill=(*_CYA, 255))
        else:
            draw.polygon([
                (cx, cy + dy*(a + ah)),
                (cx - ah, cy + dy*a),
                (cx + ah, cy + dy*a),
            ], fill=(*_CYA, 255))

    _arrow(1, 0); _arrow(-1, 0); _arrow(0, 1); _arrow(0, -1)
    draw.ellipse([cx - aw, cy - aw, cx + aw, cy + aw], fill=(*_IND, 255))


def _draw_crosshair(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Fine precision crosshair."""
    cx, cy = s // 2, s // 2
    w      = max(1, s // 28)
    gap    = s * 5 // 48
    # Horizontal
    draw.line([(s*4//48, cy), (cx - gap, cy)], fill=(*_CYA, 255), width=w)
    draw.line([(cx + gap, cy), (s*44//48, cy)], fill=(*_CYA, 255), width=w)
    # Vertical
    draw.line([(cx, s*4//48), (cx, cy - gap)], fill=(*_CYA, 255), width=w)
    draw.line([(cx, cy + gap), (cx, s*44//48)], fill=(*_CYA, 255), width=w)
    # Center dot
    r = s * 3 // 48
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*_CYA, 255))
    # Outer ring
    r2 = s * 7 // 48
    draw.arc([cx-r2, cy-r2, cx+r2, cy+r2], 0, 360, fill=(*_IND, 180), width=w)


def _draw_forbidden(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Circle with diagonal slash."""
    r  = s * 18 // 48
    cx, cy = s // 2, s // 2
    w  = max(2, s // 10)
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(220, 38, 38, 255), width=w)
    # Diagonal
    off = int(r * 0.707)
    draw.line([(cx - off, cy - off), (cx + off, cy + off)], fill=(220, 38, 38, 255), width=w)


def _draw_resize_h(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Horizontal double arrow ↔"""
    cx, cy = s // 2, s // 2
    a  = s * 18 // 48
    aw = s * 7 // 48
    w  = max(1, s // 14)
    draw.line([(cx - a, cy), (cx + a, cy)], fill=(*_CYA, 255), width=w)
    for dx in (-1, 1):
        draw.polygon([
            (cx + dx*(a+aw), cy),
            (cx + dx*a, cy - aw//2),
            (cx + dx*a, cy + aw//2),
        ], fill=(*_CYA, 255))


def _draw_resize_v(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Vertical double arrow ↕"""
    cx, cy = s // 2, s // 2
    a  = s * 18 // 48
    aw = s * 7 // 48
    w  = max(1, s // 14)
    draw.line([(cx, cy - a), (cx, cy + a)], fill=(*_CYA, 255), width=w)
    for dy in (-1, 1):
        draw.polygon([
            (cx, cy + dy*(a+aw)),
            (cx - aw//2, cy + dy*a),
            (cx + aw//2, cy + dy*a),
        ], fill=(*_CYA, 255))


def _draw_resize_diag(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Diagonal double arrow ↗↙"""
    cx, cy = s // 2, s // 2
    a  = s * 16 // 48
    aw = s * 6 // 48
    w  = max(1, s // 14)
    draw.line([(cx - a, cy + a), (cx + a, cy - a)], fill=(*_CYA, 255), width=w)
    for (dx, dy) in [(-1, 1), (1, -1)]:
        head_x = cx + dx * a
        head_y = cy + dy * a
        draw.polygon([
            (head_x, head_y),
            (head_x - dy*aw, head_y - dx*aw),
            (head_x + dx*aw//2, head_y + dy*aw//2),
        ], fill=(*_CYA, 255))


def _draw_precision(img: Image.Image, draw: ImageDraw.ImageDraw, s: int):
    """Small fine crosshair."""
    _draw_crosshair(img, draw, s)


# Map cursor name → draw function
_DRAW_FN = {
    "default":            _draw_default,
    "pointer":            _draw_pointer,
    "hand":               _draw_hand,
    "text":               _draw_text,
    "busy":               _draw_busy,
    "working":            _draw_working,
    "move":               _draw_move,
    "crosshair":          _draw_crosshair,
    "forbidden":          _draw_forbidden,
    "resize_horizontal":  _draw_resize_h,
    "resize_vertical":    _draw_resize_v,
    "resize_diagonal_nw": _draw_resize_diag,
    "resize_diagonal_ne": _draw_resize_diag,
    "precision_select":   _draw_precision,
}


def _render_cursor_png(name: str, size: int) -> Image.Image:
    """Render a cursor into an RGBA PIL image at the given size."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fn   = _DRAW_FN.get(name, _draw_default)
    fn(img, draw, size)
    # Light smooth pass for anti-aliasing
    img = img.filter(ImageFilter.SMOOTH_MORE)
    return img


# ---------------------------------------------------------------------------
# XCursor binary writer (pure Python)
# ---------------------------------------------------------------------------

XCURSOR_MAGIC   = 0x72756358   # "Xcur"
XCURSOR_VERSION = 65536        # 1.0
XCURSOR_IMAGE_TYPE = 0xFFFD0002
XCURSOR_IMAGE_SUBTYPE = 1


def _write_xcursor(images: list, out_path: str):
    """
    Write an XCursor binary file.

    images: list of (size, delay_ms, rgba_pixels_bytearray, width, height, xhot, yhot)
    """
    # TOC entry size: type(4) + subtype(4) + position(4) = 12 bytes
    header_size = 16    # magic(4) + header_size(4) + version(4) + ntoc(4)
    toc_entry_size = 12
    image_header_size = 36  # type(4)+chunk_header_len(4)+type(4)+subtype(4)+version(4)+width(4)+height(4)+xhot(4)+yhot(4)

    ntoc = len(images)
    toc_size = ntoc * toc_entry_size

    # Pre-compute chunk sizes and positions
    chunks = []
    pos = header_size + toc_size
    for sz, delay, pixels, w, h, xhot, yhot in images:
        pixel_bytes = bytes(pixels)
        chunk_size  = image_header_size + len(pixel_bytes)
        chunks.append((sz, delay, pixel_bytes, w, h, xhot, yhot, pos, chunk_size))
        pos += chunk_size

    with open(out_path, "wb") as f:
        # File header
        f.write(struct.pack("<IIII", XCURSOR_MAGIC, header_size, XCURSOR_VERSION, ntoc))
        # TOC
        for sz, delay, pixel_bytes, w, h, xhot, yhot, chunk_pos, chunk_size in chunks:
            f.write(struct.pack("<III", XCURSOR_IMAGE_TYPE, sz, chunk_pos))
        # Image chunks
        for sz, delay, pixel_bytes, w, h, xhot, yhot, chunk_pos, chunk_size in chunks:
            f.write(struct.pack(
                "<IIIIIIIII",
                image_header_size,   # chunk header length
                XCURSOR_IMAGE_TYPE,
                XCURSOR_IMAGE_SUBTYPE,
                1,                   # version
                w, h, xhot, yhot,
                delay,
            ))
            f.write(pixel_bytes)


def _pil_to_argb32(img: Image.Image) -> bytearray:
    """Convert RGBA PIL image to XCursor ARGB32 pixel data (BGRA byte order)."""
    img = img.convert("RGBA")
    w, h = img.size
    buf  = bytearray(w * h * 4)
    px   = img.load()
    idx  = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            # XCursor stores pixels as 32-bit ARGB in native endian
            val = (a << 24) | (r << 16) | (g << 8) | b
            struct.pack_into("<I", buf, idx, val)
            idx += 4
    return buf


def _generate_xcursor_theme(cursors_dir: str, cursor_name: str, hotspot: tuple):
    """Generate a single XCursor binary containing all required sizes."""
    xhot_base, yhot_base = hotspot
    images = []
    for size in XCURSOR_SIZES:
        # Scale hotspot proportionally
        xhot = int(xhot_base * size / RENDER_SIZE)
        yhot = int(yhot_base * size / RENDER_SIZE)
        img  = _render_cursor_png(cursor_name, size)
        argb = _pil_to_argb32(img)
        images.append((size, 50, argb, size, size, xhot, yhot))
    _write_xcursor(images, cursors_dir)


# ---------------------------------------------------------------------------
# Windows .cur writer
# ---------------------------------------------------------------------------

def _save_win_cur(img: Image.Image, cur_path: str, hotspot: tuple):
    """Write a valid Windows CUR file from a PIL RGBA image."""
    img = img.resize((32, 32), Image.Resampling.LANCZOS).convert("RGBA")
    xhot, yhot = hotspot

    # Encode image as BMP DIB (BITMAPINFOHEADER + XOR mask + AND mask)
    w, h = img.size
    # PNG-in-ICO trick: embed PNG data directly (Windows Vista+)
    png_buf = io.BytesIO()
    img.save(png_buf, format="PNG")
    png_data = png_buf.getvalue()

    # ICONDIR header: reserved(2) + type(2=cursor) + count(2)
    header = struct.pack("<HHH", 0, 2, 1)
    # ICONDIRENTRY: width(1) height(1) colorCount(1) reserved(1)
    #               xHotspot(2) yHotspot(2) dwBytesInRes(4) dwImageOffset(4)
    entry_offset = 6 + 16   # header(6) + one entry(16)
    entry = struct.pack("<BBBBHHII",
                        w % 256, h % 256, 0, 0,
                        xhot, yhot,
                        len(png_data), entry_offset)

    with open(cur_path, "wb") as f:
        f.write(header + entry + png_data)


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------

def generate_cursor_themes(target_root: str) -> None:
    cursors_root = ensure_dir(os.path.join(target_root, "cursors"))

    linux_theme_dir   = ensure_dir(os.path.join(cursors_root, "linux", "PyFlare", "cursors"))
    linux_parent_dir  = os.path.dirname(linux_theme_dir)
    windows_dir       = ensure_dir(os.path.join(cursors_root, "windows"))
    macos_dir         = ensure_dir(os.path.join(cursors_root, "macos"))
    png_preview_dir   = ensure_dir(os.path.join(cursors_root, "png_preview"))

    cursor_names = list(CURSOR_DEFINITIONS.keys())
    total = len(cursor_names) * (1 + len(XCURSOR_SIZES) + 2)  # XCursor + .cur + macOS

    with ProgressReporter(len(cursor_names), desc="Cursors") as prog:
        for cursor_name, hotspot in CURSOR_DEFINITIONS.items():

            # ---- 1. Render preview PNG (RENDER_SIZE) ----
            preview_img = _render_cursor_png(cursor_name, RENDER_SIZE)
            preview_img.save(
                os.path.join(png_preview_dir, f"{cursor_name}.png"), "PNG"
            )

            # ---- 2. Linux XCursor ----
            xcursor_path = os.path.join(linux_theme_dir, cursor_name)
            _generate_xcursor_theme(xcursor_path, cursor_name, hotspot)
            # Also invoke xcursorgen if available (non-critical)
            run_subprocess_safe(
                ["xcursorgen", "-", xcursor_path],
                fallback_msg="xcursorgen not installed; pure-Python XCursor used",
            )

            # ---- 3. Windows .cur ----
            cur_img = _render_cursor_png(cursor_name, 32)
            xhot_32 = int(hotspot[0] * 32 / RENDER_SIZE)
            yhot_32 = int(hotspot[1] * 32 / RENDER_SIZE)
            _save_win_cur(cur_img, os.path.join(windows_dir, f"{cursor_name}.cur"),
                          (xhot_32, yhot_32))

            # ---- 4. macOS PNG exports ----
            mac_cursor_dir = ensure_dir(os.path.join(macos_dir, cursor_name))
            for mac_size, suffix in [(32, ""), (64, "@2x")]:
                mac_img = _render_cursor_png(cursor_name, mac_size)
                mac_img.save(
                    os.path.join(mac_cursor_dir, f"{cursor_name}{suffix}.png"), "PNG"
                )
            # Hotspot metadata
            cursor_info = {
                "name":    cursor_name,
                "hotspot": {"x": hotspot[0], "y": hotspot[1]},
                "size":    RENDER_SIZE,
            }
            with open(os.path.join(mac_cursor_dir, "cursor_info.json"), "w") as f:
                json.dump(cursor_info, f, indent=2)

            prog.advance(1, postfix=cursor_name)

    # ---- Linux theme metadata files ----
    index_theme = (
        "[Icon Theme]\n"
        "Name=PyFlare\n"
        "Comment=PyFlare OS Cursor Theme\n"
        "Example=default\n"
    )
    with open(os.path.join(linux_parent_dir, "index.theme"), "w") as f:
        f.write(index_theme)

    cursor_theme = (
        "[Icon Theme]\n"
        "Inherits=PyFlare\n"
    )
    with open(os.path.join(linux_parent_dir, "cursor.theme"), "w") as f:
        f.write(cursor_theme)

    # ---- Windows install.inf scaffold ----
    inf_lines = ["[Version]\nSignature=\"$Windows NT$\"\n[DefaultInstall]\n"
                 "CopyFiles=Scheme.Cur\n[Scheme.Cur]\n"]
    for name in cursor_names:
        inf_lines.append(f"{name}.cur\n")
    with open(os.path.join(windows_dir, "install.inf"), "w") as f:
        f.writelines(inf_lines)

    logger.info(
        f"Cursors: generated {len(cursor_names)} cursors × "
        f"{len(XCURSOR_SIZES)} XCursor sizes + Windows .cur + macOS PNG"
    )
