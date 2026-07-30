"""
branding_generator/validator.py
Full asset validation with colored terminal output and JSON report.
"""
import sys
import io

# Reconfigure stdout to UTF-8 so Unicode symbols render on Windows cp1252 terminals
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
elif sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import json
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from PIL import Image
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True, strip=False, convert=False)
    _OK   = lambda s: Fore.GREEN  + s + Style.RESET_ALL
    _WARN = lambda s: Fore.YELLOW + s + Style.RESET_ALL
    _ERR  = lambda s: Fore.RED    + s + Style.RESET_ALL
    _INFO = lambda s: Fore.CYAN   + s + Style.RESET_ALL
except ImportError:
    _OK = _WARN = _ERR = _INFO = lambda s: s


def _safe_print(text: str):
    """Print text safely, replacing unencodable characters."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode('ascii'))

# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

def _check_json(file_path: str) -> list:
    errors = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
    except Exception as e:
        errors.append(f"Invalid JSON: {e}")
    return errors


def _check_png(file_path: str, root: str) -> list:
    errors = []
    try:
        with Image.open(file_path) as img:
            img.verify()
        with Image.open(file_path) as img:
            is_icon_path = any(
                seg in root for seg in ("logos", "icons", "cursors", "badges", "placeholders")
            )
            if is_icon_path and img.mode not in ("RGBA", "LA") and "transparency" not in img.info:
                errors.append("PNG missing alpha channel for an icon asset")
    except Exception as e:
        errors.append(f"Corrupted PNG: {e}")
    return errors


def _check_svg(file_path: str) -> list:
    errors = []
    try:
        tree = ET.parse(file_path)
        root_el = tree.getroot()
        # ElementTree expands xmlns into Clark notation: {http://...}tagname
        if "}" in root_el.tag:
            ns, tag = root_el.tag[1:].split("}", 1)
            # Valid SVG namespace
            if "svg" not in ns:
                errors.append(f"SVG has unexpected namespace: '{ns}'")
            if tag != "svg":
                errors.append(f"SVG root element is '{tag}', expected 'svg'")
        else:
            tag = root_el.tag
            if tag != "svg":
                errors.append(f"SVG root element is '{tag}', expected 'svg'")
            # If there's no Clark namespace the xmlns might be missing
            if not root_el.get("xmlns"):
                errors.append("SVG missing xmlns attribute")
    except Exception as e:
        errors.append(f"Invalid SVG XML: {e}")
    return errors


def _check_ico(file_path: str) -> list:
    errors = []
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
        if magic[:4] != b"\x00\x00\x01\x00" and magic[:4] != b"\x00\x00\x02\x00":
            errors.append("ICO file has invalid magic bytes")
    except Exception as e:
        errors.append(f"Cannot read ICO: {e}")
    return errors


def _check_icns(file_path: str) -> list:
    errors = []
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
        if magic != b"icns":
            errors.append("ICNS file has invalid magic bytes")
    except Exception as e:
        errors.append(f"Cannot read ICNS: {e}")
    return errors


# ---------------------------------------------------------------------------
# Expected directory structure
# ---------------------------------------------------------------------------
EXPECTED_DIRS = [
    "logos/svg", "logos/png",
    "cursors", "animations", "themes",
    "wallpapers", "colors", "badges",
    "favicon", "sounds",
]


def validate_assets(target_root: str) -> tuple:
    logger.info(_INFO("Starting comprehensive asset validation…"))

    all_errors  = []
    all_warnings= []
    hashes      = {}
    basenames   = {}
    file_count  = 0

    # Check expected directories exist
    for rel_dir in EXPECTED_DIRS:
        full = os.path.join(target_root, rel_dir)
        if not os.path.isdir(full):
            all_warnings.append(f"Expected directory missing: {rel_dir}")

    # Walk all files
    for root_dir, dirs, files in os.walk(target_root):
        # Skip __pycache__ and .build_cache
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]

        for file in files:
            file_path = os.path.join(root_dir, file)
            rel       = os.path.relpath(file_path, target_root).replace("\\", "/")
            file_count += 1

            # Empty file check
            size = os.path.getsize(file_path)
            if size == 0:
                if "screenshots" not in root_dir:
                    all_errors.append(f"Empty file: {rel}")
                continue

            # Format-specific checks
            ext = file.lower().rsplit(".", 1)[-1] if "." in file else ""
            file_errors = []
            if ext == "json":
                file_errors += _check_json(file_path)
            elif ext == "png":
                file_errors += _check_png(file_path, root_dir)
            elif ext == "svg":
                file_errors += _check_svg(file_path)
            elif ext == "ico":
                file_errors += _check_ico(file_path)
            elif ext == "icns":
                file_errors += _check_icns(file_path)

            for e in file_errors:
                all_errors.append(f"{rel}: {e}")

            # Duplicate hash detection
            try:
                with open(file_path, "rb") as fh:
                    fhash = hashlib.sha256(fh.read()).hexdigest()
                if fhash in hashes:
                    if "export" not in root_dir:
                        all_warnings.append(
                            f"Duplicate content: {rel} == {hashes[fhash]}"
                        )
                else:
                    hashes[fhash] = rel
            except Exception as e:
                all_errors.append(f"Hash error on {rel}: {e}")

            # Duplicate basename detection
            bn = file.lower()
            if bn in basenames and os.path.dirname(rel) != os.path.dirname(basenames[bn]):
                all_warnings.append(
                    f"Duplicate basename '{file}' in two directories: "
                    f"{rel} and {basenames[bn]}"
                )
            basenames[bn] = rel

    # Build report
    report = {
        "generated_at":   datetime.now().isoformat(),
        "files_checked":  file_count,
        "errors":         all_errors,
        "warnings":       all_warnings,
        "passed":         len(all_errors) == 0,
    }
    report_path = os.path.join(target_root, "validation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    _safe_print('')
    _safe_print(_INFO(f"  Files checked : {file_count}"))
    _safe_print(_OK(  f"  Errors        : {len(all_errors)}") if not all_errors
                else _ERR(f"  Errors        : {len(all_errors)}"))
    _safe_print(_WARN(f"  Warnings      : {len(all_warnings)}"))
    for e in all_errors[:20]:
        _safe_print(_ERR(f"    [FAIL] {e}"))
    for w in all_warnings[:10]:
        _safe_print(_WARN(f"    [WARN] {w}"))
    if len(all_errors) > 20:
        _safe_print(_ERR(f"    ... and {len(all_errors)-20} more errors (see validation_report.json)"))
    _safe_print('')

    if report["passed"]:
        logger.info("[OK] Validation PASSED")
    else:
        logger.error(f"[FAIL] Validation FAILED -- {len(all_errors)} errors")

    return report["passed"], all_errors
