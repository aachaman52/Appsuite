import os
import sys
import shutil
import zipfile
import argparse
import logging
from branding_generator.utils import setup_logger, ensure_dir
from branding_generator.icons import generate_all_icons
from branding_generator.cursors import generate_cursor_themes
from branding_generator.wallpapers import generate_all_wallpapers
from branding_generator.sounds import generate_all_sounds
from branding_generator.animations import generate_all_animations
from branding_generator.themes import generate_all_themes
from branding_generator.exporters import export_vector_logos
from branding_generator.validator import validate_assets
from branding_generator.manifest import generate_manifest
from branding_generator.previews import generate_all_previews
from branding_generator.docs import generate_documentation_files
from branding_generator.extras import generate_all_extras

logger = setup_logger()

def cmd_generate(target_root):
    logger.info("Initializing PyFlare branding generation...")
    generate_all_icons(target_root)
    generate_cursor_themes(target_root)
    generate_all_wallpapers(target_root)
    generate_all_sounds(target_root)
    generate_all_animations(target_root)
    generate_all_themes(target_root)
    generate_all_extras(target_root)
    export_vector_logos(target_root)
    generate_documentation_files(target_root)
    generate_all_previews(target_root)
    logger.info("Generating assets metadata...")
    generate_manifest(target_root)
    logger.info("Generation workflow completed!")


def cmd_validate(target_root):
    success, errors = validate_assets(target_root)
    if success:
        print("Validation PASSED successfully.")
    else:
        print(f"Validation FAILED with {len(errors)} errors.")
        sys.exit(1)

def cmd_clean(target_root):
    logger.info(f"Cleaning branding output folders under {target_root}")
    folders = ["logos", "icons", "wallpapers", "sounds", "animations", "themes", "login", "installer", "store", "placeholders", "docs", "badges", "favicon", "export", "colors", "mockups", "screenshots", "previews"]
    for f in folders:
        path = os.path.join(target_root, f)
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.info(f"Removed {path}")
    manifest_file = os.path.join(target_root, "manifest.json")
    if os.path.exists(manifest_file):
        os.remove(manifest_file)
    logger.info("Cleanup completed successfully.")

def cmd_package(target_root):
    pkg_dir = os.path.join(target_root, "export")
    ensure_dir(pkg_dir)
    zip_path = os.path.join(pkg_dir, "pyflare_branding_release.zip")
    logger.info(f"Packaging release to {zip_path}...")
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as release_zip:
        for root, dirs, files in os.walk(target_root):
            for file in files:
                if file == "pyflare_branding_release.zip":
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, target_root)
                release_zip.write(file_path, rel_path)
                
    logger.info("Packaging release completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="PyFlare Branding Ecosystem Pipeline Manager")
    parser.add_argument("command", choices=["generate", "validate", "export", "preview", "clean", "package", "stats"])
    parser.add_argument("--root", default=r"c:\Users\91629\OneDrive\เอกสาร\Desktop\Appsuite\PyFlare\branding", help="Target root directory")
    parser.add_argument("--verbose", action="store_true", help="Print verbose logs")
    
    args = parser.parse_args()
    
    global logger
    logger = setup_logger(args.verbose)
    
    if args.command == "generate":
        cmd_generate(args.root)
    elif args.command == "validate":
        cmd_validate(args.root)
    elif args.command == "clean":
        cmd_clean(args.root)
    elif args.command == "package":
        cmd_package(args.root)
    elif args.command == "preview":
        generate_all_previews(args.root)
    elif args.command == "export":
        export_vector_logos(args.root)
    elif args.command == "stats":
        if os.path.exists(os.path.join(args.root, "manifest.json")):
            with open(os.path.join(args.root, "manifest.json")) as f:
                data = json.load(f)
            print(f"Total compiled assets tracked: {len(data.get('assets', {}))}")
        else:
            print("No manifest.json found. Run generate first.")

if __name__ == "__main__":
    main()
