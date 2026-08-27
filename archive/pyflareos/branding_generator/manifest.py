"""
branding_generator/manifest.py
Extended asset manifest with version, asset_type, supported_platforms,
category, dimensions, SHA-256, file size, and creation date.
"""

import os
import json
import hashlib
import datetime
import logging
from PIL import Image
from branding_generator.config import VERSION

logger = logging.getLogger("pyflare-brand")

# Extension → asset_type mapping
_EXT_TYPE = {
    "svg":  "vector",
    "pdf":  "vector",
    "eps":  "vector",
    "png":  "raster",
    "jpg":  "raster",
    "jpeg": "raster",
    "webp": "raster",
    "gif":  "animation",
    "mp4":  "animation",
    "json": "data",
    "ico":  "icon",
    "icns": "icon",
    "cur":  "cursor",
    "ani":  "cursor",
    "wav":  "audio",
    "css":  "theme",
    "qss":  "theme",
    "scss": "theme",
    "qml":  "theme",
    "toml": "data",
    "yaml": "data",
    "md":   "documentation",
    "txt":  "documentation",
    "inf":  "metadata",
}

# Path segment → platform hint
_PLATFORM_HINTS = {
    "linux":   ["linux"],
    "windows": ["windows"],
    "macos":   ["macos"],
    "xcursor": ["linux"],
    "gtk":     ["linux"],
    "kde":     ["linux"],
    "vscode":  ["linux", "windows", "macos"],
    "terminal":["linux", "windows", "macos"],
    "favicon": ["web"],
    "social":  ["web"],
    "android": ["android"],
    "ios":     ["ios"],
}

_SKIP_FILES = {"manifest.json", "validation_report.json", ".build_cache.json"}


def _get_dimensions(file_path: str, ext: str) -> str | None:
    if ext in ("png", "jpg", "jpeg", "webp", "gif"):
        try:
            with Image.open(file_path) as img:
                return f"{img.width}x{img.height}"
        except Exception:
            pass
    return None


def _get_platforms(rel_path: str) -> list:
    parts = rel_path.lower().replace("\\", "/").split("/")
    platforms = set()
    for part in parts:
        for hint, plats in _PLATFORM_HINTS.items():
            if hint in part:
                platforms.update(plats)
    if not platforms:
        platforms.add("universal")
    return sorted(platforms)


def _get_category(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    return parts[0] if parts else "misc"


def generate_manifest(target_root: str) -> None:
    logger.info("Generating manifest.json…")

    manifest = {
        "name":         "PyFlare Branding Manifest",
        "version":      VERSION,
        "generated_at": datetime.datetime.now().isoformat(),
        "generator":    "PyFlare Branding Generator",
        "assets":       {},
    }

    for root_dir, dirs, files in os.walk(target_root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for file in files:
            if file in _SKIP_FILES:
                continue
            file_path = os.path.join(root_dir, file)
            rel_path  = os.path.relpath(file_path, target_root).replace("\\", "/")
            ext = file.rsplit(".", 1)[-1].lower() if "." in file else ""

            stat      = os.stat(file_path)
            size      = stat.st_size
            created   = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()

            sha256 = ""
            try:
                h = hashlib.sha256()
                with open(file_path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                sha256 = h.hexdigest()
            except Exception:
                pass

            manifest["assets"][rel_path] = {
                "version":            VERSION,
                "size_bytes":         size,
                "created_at":         created,
                "sha256":             sha256,
                "dimensions":         _get_dimensions(file_path, ext),
                "asset_type":         _EXT_TYPE.get(ext, "unknown"),
                "category":           _get_category(rel_path),
                "supported_platforms": _get_platforms(rel_path),
            }

    out_path = os.path.join(target_root, "manifest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Manifest: tracked {len(manifest['assets'])} assets → manifest.json")
