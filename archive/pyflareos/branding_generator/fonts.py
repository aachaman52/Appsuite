"""
branding_generator/fonts.py  [NEW]
Font packaging: download Inter, Space Grotesk, JetBrains Mono,
cache locally, write font_manifest.json, generate font_preview.png.
"""

import os
import json
import logging
import zipfile
import hashlib
from datetime import datetime
from PIL import Image, ImageDraw
from branding_generator.config import FONT_SOURCES, BRAND_COLORS
from branding_generator.utils import ensure_dir, hex_to_rgb

logger = logging.getLogger("pyflare-brand")

_BG   = hex_to_rgb(BRAND_COLORS["background"])
_SURF = hex_to_rgb(BRAND_COLORS["surface"])
_IND  = hex_to_rgb(BRAND_COLORS["indigo"])
_CYA  = hex_to_rgb(BRAND_COLORS["cyan"])
_WHT  = (255, 255, 255)

CACHE_DIR_NAME = ".font_cache"


def _download_file(url: str, dest: str) -> bool:
    try:
        import requests
        logger.info(f"Downloading {url} …")
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except ImportError:
        logger.warning("requests not installed — font download skipped")
        return False
    except Exception as e:
        logger.warning(f"Font download failed ({url}): {e}")
        return False


def _extract_zip(zip_path: str, extract_dir: str, wanted_exts: tuple = (".ttf", ".otf")) -> list:
    found = []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if any(name.lower().endswith(ext) for ext in wanted_exts):
                    z.extract(name, extract_dir)
                    found.append(os.path.join(extract_dir, name))
    except Exception as e:
        logger.warning(f"ZIP extract error: {e}")
    return found


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except Exception:
        pass
    return h.hexdigest()


def _generate_font_preview(fonts_dir: str, font_files: dict):
    """
    Generate font_preview.png showing sample text for each font.
    Uses PIL's default font (real font loading requires font path).
    """
    ROW_H = 80
    IMG_W = 900
    IMG_H = ROW_H * (len(font_files) + 1) + 20
    img   = Image.new("RGBA", (IMG_W, IMG_H), (*_BG, 255))
    draw  = ImageDraw.Draw(img)

    # Header bar
    draw.rectangle([0, 0, IMG_W, 40], fill=(*_IND, 200))

    y = 48
    samples = {
        "Inter":           "Inter — The quick brown fox jumps over the lazy dog",
        "Space Grotesk":   "Space Grotesk — ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789",
        "JetBrains Mono":  "JetBrains Mono — def main(): return 'PyFlare'",
    }
    for font_name, files in font_files.items():
        text = samples.get(font_name, font_name + " — sample text")
        draw.rectangle([20, y, IMG_W - 20, y + ROW_H - 8],
                        fill=(*_SURF, 200), outline=(*_IND, 60), width=1)
        # Font name label
        draw.text((32, y + 8),  font_name, fill=(*_CYA, 255))
        # Sample text
        draw.text((32, y + 30), text[:72], fill=(*_WHT, 200))
        # File list
        draw.text((32, y + 52), f"{len(files)} file(s)", fill=(*_IND, 180))
        y += ROW_H

    img.save(os.path.join(fonts_dir, "font_preview.png"), "PNG")


def generate_fonts(target_root: str) -> None:
    fonts_dir  = ensure_dir(os.path.join(target_root, "fonts"))
    cache_dir  = ensure_dir(os.path.join(fonts_dir, CACHE_DIR_NAME))

    manifest_entries = {}
    installed_fonts  = {}

    for font_name, font_cfg in FONT_SOURCES.items():
        url      = font_cfg["url"]
        license_ = font_cfg["license"]
        font_dir = ensure_dir(os.path.join(fonts_dir, font_name.replace(" ", "_")))

        # Determine cache zip filename
        zip_name = url.rsplit("/", 1)[-1].split("?")[0] or f"{font_name}.zip"
        zip_path = os.path.join(cache_dir, zip_name)

        ttf_files = []

        # Download if not cached
        if not os.path.exists(zip_path):
            ok = _download_file(url, zip_path)
            if not ok:
                # Create a placeholder manifest entry anyway
                manifest_entries[font_name] = {
                    "name": font_name, "license": license_,
                    "status": "download_failed", "files": [],
                }
                continue

        # Extract
        ttf_files = _extract_zip(zip_path, font_dir)
        if not ttf_files:
            # Some Google Fonts zips have flat structure
            ttf_files = [
                os.path.join(font_dir, f)
                for f in os.listdir(font_dir)
                if f.lower().endswith((".ttf", ".otf"))
            ]

        installed_fonts[font_name] = ttf_files

        file_entries = []
        for fpath in ttf_files:
            if os.path.exists(fpath):
                file_entries.append({
                    "filename": os.path.relpath(fpath, fonts_dir).replace("\\", "/"),
                    "size_bytes": os.path.getsize(fpath),
                    "sha256": _sha256_file(fpath),
                })

        manifest_entries[font_name] = {
            "name":    font_name,
            "license": license_,
            "source":  url,
            "status":  "installed",
            "files":   file_entries,
        }

    # Write font_manifest.json
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "fonts": manifest_entries,
    }
    with open(os.path.join(fonts_dir, "font_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # Write per-font license stubs
    for font_name, cfg in FONT_SOURCES.items():
        lic_path = os.path.join(fonts_dir, font_name.replace(" ", "_"), "LICENSE.txt")
        if not os.path.exists(lic_path):
            with open(lic_path, "w") as f:
                f.write(f"{font_name}\n{cfg['license']}\nSource: {cfg['url']}\n")

    # Generate font preview
    _generate_font_preview(fonts_dir, installed_fonts)

    logger.info(
        f"Fonts: processed {len(manifest_entries)} font families, "
        f"wrote font_manifest.json and font_preview.png"
    )
