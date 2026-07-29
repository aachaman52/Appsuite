import os
import json
import hashlib
import logging
from PIL import Image

logger = logging.getLogger("pyflare-brand")

def validate_assets(target_root):
    logger.info("Starting asset validation...")
    errors = []
    hashes = {}
    
    for root, dirs, files in os.walk(target_root):
        for file in files:
            file_path = os.path.join(root, file)
            
            # 1. Check for empty files
            if os.path.getsize(file_path) == 0:
                # Allow empty screenshot placeholders
                if "screenshots" not in root:
                    errors.append(f"Empty file: {file_path}")
                continue
                
            # 2. Check JSON validity
            if file.endswith(".json"):
                try:
                    with open(file_path, "r") as f:
                        json.load(f)
                except Exception as e:
                    errors.append(f"Invalid JSON in {file_path}: {e}")
                    
            # 3. Check PNG validity and transparency
            if file.endswith(".png"):
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                    # Reopen for transparency check
                    with Image.open(file_path) as img:
                        if img.mode not in ("RGBA", "LA") and "transparency" not in img.info:
                            # Allow wallpapers to not have transparency
                            if "wallpapers" not in root and "login" not in root and "ui" not in root:
                                errors.append(f"PNG lacks alpha channel: {file_path}")
                except Exception as e:
                    errors.append(f"Corrupted PNG {file_path}: {e}")
                    
            # 4. Check for duplicate file hashes (accidental copies)
            try:
                with open(file_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if file_hash in hashes:
                    # Ignore intentional exports duplicates
                    if "export" not in root:
                        logger.warning(f"Duplicate hash detected between {file_path} and {hashes[file_hash]}")
                else:
                    hashes[file_hash] = file_path
            except Exception as e:
                errors.append(f"Failed to hash {file_path}: {e}")
                
    if len(errors) == 0:
        logger.info("All assets passed validation checks perfectly!")
        return True, []
    else:
        logger.error(f"Asset validation failed with {len(errors)} errors:")
        for err in errors:
            logger.error(f"  - {err}")
        return False, errors
