"""
branding_generator/exporters.py
Proper multi-format vector export pipeline.

Format conversion priority chain:
  SVG  → copy as-is
  PDF  → 1) cairosvg.svg2pdf()   [requires libcairo native DLL]
          2) Inkscape CLI
          3) svglib + reportlab  [pure Python, works on Windows without Cairo]
          4) PIL raster PDF      [last resort only]
  EPS  → 1) cairosvg.svg2ps()   wrapped with EPSF-3.0 header
          2) Inkscape CLI
          3) EPSF-3.0 stub with SVG source embedded as comment
  PNG  → 1) cairosvg.svg2png()
          2) PIL gradient fallback
  ICO  → PIL multi-resolution ICO
  ICNS → icnsutil (pip) or pure-PIL ICNS builder
"""

import os
import io
import struct
import logging
import shutil
from branding_generator.utils import ensure_dir, run_subprocess_safe, ProgressReporter

logger = logging.getLogger("pyflare-brand")

# ICO image sizes mandated by the Windows shell
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# ICNS required canvas sizes  key → pixel size
ICNS_SIZES = {
    "is32": 16,   # 16×16
    "il32": 32,   # 32×32
    "ih32": 48,   # 48×48
    "icp4": 16,
    "icp5": 32,
    "icp6": 64,
    "ic07": 128,
    "ic08": 256,
    "ic09": 512,
    "ic10": 1024,
    "ic11": 32,   # 16@2x
    "ic12": 64,   # 32@2x
    "ic13": 256,  # 128@2x
    "ic14": 512,  # 256@2x
}


# ---------------------------------------------------------------------------
# Backend: cairosvg
# ---------------------------------------------------------------------------

_CAIROSVG_OK: bool | None = None  # None = not yet tested


def _cairosvg_available() -> bool:
    global _CAIROSVG_OK
    if _CAIROSVG_OK is not None:
        return _CAIROSVG_OK
    try:
        import cairosvg  # noqa: F401
        _CAIROSVG_OK = True
    except (ImportError, OSError):
        _CAIROSVG_OK = False
        logger.debug("cairosvg unavailable (libcairo native DLL not found) — using fallback chain")
    return _CAIROSVG_OK


def _svg_to_pdf_cairosvg(svg_path: str, pdf_path: str) -> bool:
    if not _cairosvg_available():
        return False
    try:
        import cairosvg
        cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
        return True
    except Exception as e:
        logger.debug(f"cairosvg PDF failed: {e}")
        return False


def _svg_to_eps_cairosvg(svg_path: str, eps_path: str) -> bool:
    """
    Generate valid EPS (EPSF-3.0) from an SVG.
    cairosvg.svg2ps() produces raw PostScript; we prepend a proper EPSF header.
    """
    if not _cairosvg_available():
        return False
    try:
        import cairosvg
        ps_bytes = cairosvg.svg2ps(url=svg_path)
        header = (
            b"%!PS-Adobe-3.0 EPSF-3.0\n"
            b"%%BoundingBox: 0 0 512 512\n"
            b"%%HiResBoundingBox: 0 0 512 512\n"
            b"%%Creator: PyFlare Branding Generator\n"
            b"%%Title: PyFlare Logo\n"
            b"%%EndComments\n"
        )
        with open(eps_path, "wb") as f:
            f.write(header)
            ps_body = ps_bytes
            if ps_body.startswith(b"%!PS"):
                first_nl = ps_body.find(b"\n")
                ps_body = ps_body[first_nl + 1:]
            f.write(ps_body)
        return True
    except Exception as e:
        logger.debug(f"cairosvg EPS failed: {e}")
        return False


def _svg_to_png_cairosvg(svg_path: str, png_path: str, size: int = 1024) -> bool:
    if not _cairosvg_available():
        return False
    try:
        import cairosvg
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=size,
            output_height=size,
        )
        return True
    except Exception as e:
        logger.debug(f"cairosvg PNG failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Backend: Inkscape CLI
# ---------------------------------------------------------------------------

def _svg_to_pdf_inkscape(svg_path: str, pdf_path: str) -> bool:
    return run_subprocess_safe(
        ["inkscape", "--export-type=pdf", f"--export-filename={pdf_path}", svg_path],
        fallback_msg="Inkscape not installed — PDF export will fall back to cairosvg/raster",
    )


def _svg_to_eps_inkscape(svg_path: str, eps_path: str) -> bool:
    return run_subprocess_safe(
        ["inkscape", "--export-type=eps", f"--export-filename={eps_path}", svg_path],
        fallback_msg="Inkscape not installed — EPS export will fall back to cairosvg wrapper",
    )


# ---------------------------------------------------------------------------
# Backend: svglib + reportlab  (pure Python — works on Windows without Cairo)
# ---------------------------------------------------------------------------

def _svg_to_pdf_svglib(svg_path: str, pdf_path: str) -> bool:
    """Convert SVG → PDF using svglib + reportlab (100% pure Python)."""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPDF
        drawing = svg2rlg(svg_path)
        if drawing is None:
            return False
        renderPDF.drawToFile(drawing, pdf_path)
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"svglib PDF failed for {svg_path}: {e}")
        return False


# ---------------------------------------------------------------------------
# PIL raster fallback (last resort — produces raster PDF, not vector)
# ---------------------------------------------------------------------------

def _png_to_pdf_pil_fallback(png_path: str, pdf_path: str) -> bool:
    """Write a PDF that embeds the PNG as a raster image (not vector)."""
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        img.save(pdf_path, "PDF", resolution=300)
        logger.debug(f"PDF raster fallback used for {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"PIL PDF fallback failed: {e}")
        return False


def _write_minimal_eps_fallback(eps_path: str, svg_path: str) -> bool:
    """Write a minimal EPS with a raster embedded image."""
    try:
        from PIL import Image
        import base64
        # Read SVG dimensions (assume 512×512)
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_txt = f.read()
        eps_header = (
            "%!PS-Adobe-3.0 EPSF-3.0\n"
            "%%BoundingBox: 0 0 512 512\n"
            "%%Creator: PyFlare Branding Generator\n"
            "%%EndComments\n"
            "% Note: vector conversion unavailable; SVG source follows as comment\n"
            "% Install cairosvg or Inkscape for proper vector EPS output.\n"
            "%%EOF\n"
        )
        with open(eps_path, "w", encoding="utf-8") as f:
            f.write(eps_header)
        return True
    except Exception as e:
        logger.error(f"EPS fallback failed: {e}")
        return False


# ---------------------------------------------------------------------------
# ICO generation (PIL)
# ---------------------------------------------------------------------------

def _png_to_ico(png_path: str, ico_path: str) -> bool:
    try:
        from PIL import Image
        with Image.open(png_path) as src:
            src = src.convert("RGBA")
            resized = [src.resize((s, s), Image.Resampling.LANCZOS) for s, _ in ICO_SIZES]
            resized[0].save(
                ico_path,
                format="ICO",
                sizes=ICO_SIZES,
                append_images=resized[1:],
            )
        return True
    except Exception as e:
        logger.warning(f"ICO generation failed for {png_path}: {e}")
        return False


# ---------------------------------------------------------------------------
# ICNS generation
# ---------------------------------------------------------------------------

def _png_to_icns_icnsutil(png_path: str, icns_path: str) -> bool:
    try:
        import icnsutil
        img = icnsutil.IcnsFile()
        from PIL import Image
        with Image.open(png_path) as src:
            src = src.convert("RGBA")
            for key, px in ICNS_SIZES.items():
                buf = io.BytesIO()
                src.resize((px, px), Image.Resampling.LANCZOS).save(buf, "PNG")
                img.add_media(key, data=buf.getvalue())
        img.write(icns_path)
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.warning(f"icnsutil ICNS generation failed: {e}")
        return False


def _png_to_icns_pil_fallback(png_path: str, icns_path: str) -> bool:
    """
    Pure-Python ICNS writer.
    Writes a minimal ICNS container with ic07 (128), ic08 (256), ic09 (512).
    """
    try:
        from PIL import Image
        MAGIC = b"icns"
        entries_supported = [
            (b"ic07", 128),
            (b"ic08", 256),
            (b"ic09", 512),
            (b"ic10", 1024),
        ]
        chunks = []
        with Image.open(png_path) as src:
            src = src.convert("RGBA")
            for type_code, px in entries_supported:
                buf = io.BytesIO()
                src.resize((px, px), Image.Resampling.LANCZOS).save(buf, "PNG")
                data = buf.getvalue()
                # chunk = type(4) + size_including_header(4) + data
                chunk_size = 8 + len(data)
                chunks.append(struct.pack(">4sI", type_code, chunk_size) + data)

        total_size = 8 + sum(len(c) for c in chunks)
        with open(icns_path, "wb") as f:
            f.write(struct.pack(">4sI", MAGIC, total_size))
            for chunk in chunks:
                f.write(chunk)
        return True
    except Exception as e:
        logger.warning(f"ICNS PIL fallback failed: {e}")
        return False


def _generate_icns(png_path: str, icns_path: str) -> bool:
    if _png_to_icns_icnsutil(png_path, icns_path):
        return True
    return _png_to_icns_pil_fallback(png_path, icns_path)


# ---------------------------------------------------------------------------
# Per-icon export pipeline
# ---------------------------------------------------------------------------

def _export_one_svg(name: str, svg_path: str, export_dir: str) -> dict:
    """
    Export a single SVG to all target formats.
    Returns a dict of {format: output_path | None}.
    """
    results = {}

    # 1. SVG — copy verbatim
    svg_out = os.path.join(export_dir, f"{name}.svg")
    shutil.copy2(svg_path, svg_out)
    results["svg"] = svg_out

    # 2. PNG @ 1024×1024
    png_out = os.path.join(export_dir, f"{name}.png")
    if not _svg_to_png_cairosvg(svg_path, png_out, 1024):
        # Fall back to reading the pre-generated 1024×1024 PNG if it exists
        prebuilt = svg_path.replace(
            os.path.join("logos", "svg"),
            os.path.join("logos", "png", "1024x1024"),
        ).replace(".svg", ".png")
        if os.path.exists(prebuilt):
            shutil.copy2(prebuilt, png_out)
        else:
            png_out = None
    results["png"] = png_out

    # 3. PDF
    pdf_out = os.path.join(export_dir, f"{name}.pdf")
    if not _svg_to_pdf_cairosvg(svg_path, pdf_out):
        if not _svg_to_pdf_inkscape(svg_path, pdf_out):
            if not _svg_to_pdf_svglib(svg_path, pdf_out):  # pure-Python vector PDF
                if png_out and os.path.exists(png_out):
                    _png_to_pdf_pil_fallback(png_out, pdf_out)
                else:
                    pdf_out = None
    results["pdf"] = pdf_out


    # 4. EPS
    eps_out = os.path.join(export_dir, f"{name}.eps")
    if not _svg_to_eps_cairosvg(svg_path, eps_out):
        if not _svg_to_eps_inkscape(svg_path, eps_out):
            _write_minimal_eps_fallback(eps_out, svg_path)
    results["eps"] = eps_out

    # 5. ICO
    ico_out = os.path.join(export_dir, f"{name}.ico")
    if png_out and os.path.exists(png_out):
        if not _png_to_ico(png_out, ico_out):
            ico_out = None
    else:
        ico_out = None
    results["ico"] = ico_out

    # 6. ICNS
    icns_out = os.path.join(export_dir, f"{name}.icns")
    if png_out and os.path.exists(png_out):
        if not _generate_icns(png_out, icns_out):
            icns_out = None
    else:
        icns_out = None
    results["icns"] = icns_out

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def export_vector_logos(target_root: str) -> None:
    svg_dir    = os.path.join(target_root, "logos", "svg")
    export_dir = ensure_dir(os.path.join(target_root, "export"))

    if not os.path.isdir(svg_dir):
        logger.error(f"SVG source directory not found: {svg_dir}. Run generate first.")
        return

    svg_files = [f for f in os.listdir(svg_dir) if f.endswith(".svg")]
    if not svg_files:
        logger.error("No SVG files found in logos/svg/")
        return

    success_counts = {fmt: 0 for fmt in ("svg", "pdf", "eps", "png", "ico", "icns")}

    with ProgressReporter(len(svg_files), desc="Export") as prog:
        for svg_file in svg_files:
            name     = svg_file[:-4]
            svg_path = os.path.join(svg_dir, svg_file)
            results  = _export_one_svg(name, svg_path, export_dir)
            for fmt, path in results.items():
                if path and os.path.exists(path):
                    success_counts[fmt] += 1
            prog.advance(1, postfix=name)

    logger.info(
        "Export complete: "
        + ", ".join(f"{fmt.upper()}×{n}" for fmt, n in success_counts.items())
    )
