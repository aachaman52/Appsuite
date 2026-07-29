import os
import json
import logging
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_documentation_files(target_root):
    docs_dir = os.path.join(target_root, "docs")
    ensure_dir(docs_dir)
    
    # Generate README.md
    readme_content = '''# PyFlare Branding System

Welcome to the PyFlare Visual Identity and Branding System. This folder contains all the official resources, icons, themes, wallpapers, and templates for PyFlare.

## Project Structure
- `logos/`: Standard vector and raster logos.
- `icons/`: Unified app icons, mimetype badges, system shortcuts, and folders.
- `wallpapers/`: Modern 4K desktop wallpapers.
- `login/`: Lockscreen, login backgrounds, avatars & UI icons.
- `installer/`: Setup page banners and illustrations.
- `ui/`: Settings page backgrounds, welcome banners, and layout grids.
- `social/`: Profile headers for X, LinkedIn, Discord, and Reddit.
- `colors/`: Design swatches and color configs.
- `cursors/`: Linux XCursor and Windows CUR cursor schemes.
- `sounds/`: Futuristic audio soundscapes (.wav).
- `animations/`: Frame sequences for loading and boots.
- `badges/`: SVG/PNG ecosystem badges.
- `themes/`: GTK, VS Code, and terminal JSON/CSS configurations.

## Visual Standards
- Primary Colors: Electric Indigo (`#5B5FFF`), Vibrant Cyan (`#00D4FF`), and Deep Violet.
- Background Surface: Matte dark navy (`#0B0F19`).
- Typography: Inter (UI), Space Grotesk (Headers), and JetBrains Mono (Terminal).
'''
    with open(os.path.join(target_root, "README.md"), "w") as f:
        f.write(readme_content)
        
    # Generate CHANGELOG.md
    changelog_content = '''# Changelog

## [1.0.0] - 2026-07-29
- Restructured entire workspace naming from Appsuite to PyFlare.
- Unified 80+ assets under the electric indigo and cyan visual guidelines.
- Created custom theme sheets for Dark, Light, and Midnight layouts.
- Auto-generated manifest.json and validated asset dimensions.
'''
    with open(os.path.join(docs_dir, "CHANGELOG.md"), "w") as f:
        f.write(changelog_content)
        
    # Generate LICENSE Summary
    license_content = '''PyFlare Proprietary Design License

Copyright (c) 2026 PyFlare Project. All rights reserved.

All branding designs, logos, wallpapers, and assets remain proprietary property of the PyFlare developers unless explicitly documented otherwise.
'''
    with open(os.path.join(docs_dir, "LICENSE"), "w") as f:
        f.write(license_content)
        
    logger.info("Successfully generated project documentation files")
