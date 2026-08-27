"""
branding_generator/main.py
PyFlare Branding Ecosystem Pipeline Manager — production CLI.

Commands:
  generate   Full build (icons → cursors → wallpapers → sounds → animations →
             themes → extras → fonts → export → docs → previews → manifest)
  validate   Run comprehensive asset validation + report
  export     Re-export vector formats only
  preview    Regenerate preview sheets only
  clean      Remove all generated output folders
  package    Create release ZIP archives (full + 4 sub-packages)
  stats      Print manifest statistics

Flags:
  --root ROOT         Output root directory (default: ./branding)
  --verbose           Debug-level logging
  --incremental       Skip assets whose source hash is unchanged
  --jobs N            Parallel worker count (default: 1)
  --release           Maximum quality mode (larger wallpapers, more frames)
"""

import os
import sys
import json
import time
import shutil
import zipfile
import argparse
import logging

from branding_generator.utils import setup_logger, ensure_dir, BuildCache
from branding_generator.icons      import generate_all_icons
from branding_generator.cursors    import generate_cursor_themes
from branding_generator.wallpapers import generate_all_wallpapers
from branding_generator.sounds     import generate_all_sounds
from branding_generator.animations import generate_all_animations
from branding_generator.themes     import generate_all_themes
from branding_generator.exporters  import export_vector_logos
from branding_generator.validator  import validate_assets
from branding_generator.manifest   import generate_manifest
from branding_generator.previews   import generate_all_previews
from branding_generator.docs       import generate_documentation_files
from branding_generator.extras     import generate_all_extras
from branding_generator.fonts      import generate_fonts

logger = setup_logger()

DEFAULT_ROOT = os.path.join(os.getcwd(), "branding")
CACHE_FILE   = ".build_cache.json"


# ---------------------------------------------------------------------------
# Pipeline stages with timing
# ---------------------------------------------------------------------------

def _run_stage(name: str, fn, *args, stats: dict = None, **kwargs):
    t0 = time.perf_counter()
    try:
        fn(*args, **kwargs)
    except Exception as e:
        logger.error(f"Stage '{name}' failed: {e}")
        raise
    elapsed = time.perf_counter() - t0
    logger.info(f"  ✓ {name:<30} {elapsed:.1f}s")
    if stats is not None:
        stats[name] = round(elapsed, 3)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_generate(target_root: str, incremental: bool = False, release: bool = False):
    logger.info(f"PyFlare branding generation → {target_root}")
    cache = BuildCache(os.path.join(target_root, CACHE_FILE))
    stats = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stages": {}}
    t_total = time.perf_counter()

    _run_stage("icons",      generate_all_icons,    target_root, cache, incremental, stats=stats["stages"])
    _run_stage("cursors",    generate_cursor_themes, target_root, stats=stats["stages"])
    _run_stage("wallpapers", generate_all_wallpapers,target_root, stats=stats["stages"])
    _run_stage("sounds",     generate_all_sounds,    target_root, stats=stats["stages"])
    _run_stage("animations", generate_all_animations,target_root, stats=stats["stages"])
    _run_stage("themes",     generate_all_themes,    target_root, stats=stats["stages"])
    _run_stage("extras",     generate_all_extras,    target_root, stats=stats["stages"])
    _run_stage("fonts",      generate_fonts,         target_root, stats=stats["stages"])
    _run_stage("export",     export_vector_logos,    target_root, stats=stats["stages"])
    _run_stage("docs",       generate_documentation_files, target_root, stats, stats=stats["stages"])
    _run_stage("previews",   generate_all_previews,  target_root, stats=stats["stages"])

    # Manifest last (needs all files in place)
    _run_stage("manifest",   generate_manifest,      target_root, stats=stats["stages"])

    stats["total_seconds"] = round(time.perf_counter() - t_total, 2)
    cache.save()
    logger.info(f"Generation complete in {stats['total_seconds']:.1f}s")

    # Auto-validate
    success, errors = validate_assets(target_root)
    if not success:
        logger.warning(f"{len(errors)} validation errors — see validation_report.json")


def cmd_validate(target_root: str):
    success, errors = validate_assets(target_root)
    if success:
        print("Validation PASSED ✓")
    else:
        print(f"Validation FAILED — {len(errors)} errors")
        sys.exit(1)


def cmd_clean(target_root: str):
    logger.info(f"Cleaning {target_root}")
    folders = [
        "logos", "icons", "wallpapers", "sounds", "animations", "themes",
        "login", "installer", "store", "placeholders", "docs", "badges",
        "favicon", "export", "colors", "mockups", "screenshots", "previews",
        "social", "ui", "splash", "cursors", "fonts",
    ]
    for folder in folders:
        path = os.path.join(target_root, folder)
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.info(f"  removed {folder}/")
    for fname in ("manifest.json", "validation_report.json", CACHE_FILE, "README.md"):
        fp = os.path.join(target_root, fname)
        if os.path.exists(fp):
            os.remove(fp)
    logger.info("Clean complete.")


def _zip_folder(src_root: str, sub_folder: str, zip_path: str, exclude_zip: str = ""):
    full_src = os.path.join(src_root, sub_folder)
    if not os.path.isdir(full_src):
        return
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(full_src):
            for file in files:
                fp  = os.path.join(root_dir, file)
                arc = os.path.relpath(fp, src_root)
                if fp != exclude_zip:
                    zf.write(fp, arc)


def cmd_package(target_root: str):
    pkg_dir = ensure_dir(os.path.join(target_root, "export"))
    logger.info(f"Packaging releases → {pkg_dir}")

    # Sub-packages
    sub_packages = {
        "pyflare_icons.zip":     "logos",
        "pyflare_cursors.zip":   "cursors",
        "pyflare_themes.zip":    "themes",
        "pyflare_wallpapers.zip":"wallpapers",
    }
    for zip_name, folder in sub_packages.items():
        zip_path = os.path.join(pkg_dir, zip_name)
        _zip_folder(target_root, folder, zip_path)
        logger.info(f"  → {zip_name}")

    # Full release
    full_zip = os.path.join(pkg_dir, "pyflare_branding_release.zip")
    with zipfile.ZipFile(full_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(target_root):
            for file in files:
                fp  = os.path.join(root_dir, file)
                arc = os.path.relpath(fp, target_root)
                if fp != full_zip and not arc.startswith(CACHE_FILE):
                    zf.write(fp, arc)
    logger.info(f"  → pyflare_branding_release.zip")
    logger.info("Packaging complete.")


def cmd_stats(target_root: str):
    manifest_path = os.path.join(target_root, "manifest.json")
    if not os.path.exists(manifest_path):
        print("No manifest.json found. Run 'generate' first.")
        sys.exit(1)
    with open(manifest_path, "r") as f:
        data = json.load(f)
    assets = data.get("assets", {})
    total_bytes = sum(a.get("size_bytes", 0) for a in assets.values())
    by_type = {}
    by_cat  = {}
    for meta in assets.values():
        t = meta.get("asset_type", "unknown")
        c = meta.get("category", "misc")
        by_type[t] = by_type.get(t, 0) + 1
        by_cat[c]  = by_cat.get(c, 0)  + 1
    print(f"\n  PyFlare Branding Statistics")
    print(f"  Version      : {data.get('version', '—')}")
    print(f"  Generated at : {data.get('generated_at', '—')}")
    print(f"  Total assets : {len(assets)}")
    print(f"  Total size   : {total_bytes / 1024 / 1024:.1f} MB\n")
    print("  By type:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t:<20} {n}")
    print("\n  By category:")
    for c, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"    {c:<20} {n}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="pyflare-brand",
        description="PyFlare Branding Ecosystem Pipeline Manager",
    )
    parser.add_argument(
        "command",
        choices=["generate", "validate", "export", "preview", "clean", "package", "stats"],
        help="Pipeline command to run",
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help=f"Output root directory (default: {DEFAULT_ROOT})",
    )
    parser.add_argument("--verbose",     action="store_true", help="Enable debug logging")
    parser.add_argument("--incremental", action="store_true", help="Skip unchanged assets")
    parser.add_argument("--release",     action="store_true", help="Maximum quality mode")
    parser.add_argument("--jobs",        type=int, default=1,  help="Parallel worker count")

    args = parser.parse_args()

    global logger
    logger = setup_logger(args.verbose)

    root = os.path.abspath(args.root)
    ensure_dir(root)

    if args.command == "generate":
        cmd_generate(root, incremental=args.incremental, release=args.release)
    elif args.command == "validate":
        cmd_validate(root)
    elif args.command == "clean":
        cmd_clean(root)
    elif args.command == "package":
        cmd_package(root)
    elif args.command == "preview":
        generate_all_previews(root)
    elif args.command == "export":
        export_vector_logos(root)
    elif args.command == "stats":
        cmd_stats(root)


if __name__ == "__main__":
    main()
