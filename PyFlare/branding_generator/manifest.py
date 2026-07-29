import os
import json
import hashlib
import datetime
import logging
from PIL import Image

logger = logging.getLogger("pyflare-brand")

def get_file_metadata(file_path):
    stat = os.stat(file_path)
    size = stat.st_size
    created = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
    
    # Get dimensions for images
    dimensions = None
    if file_path.endswith((".png", ".jpg", ".jpeg", ".webp")):
        try:
            with Image.open(file_path) as img:
                dimensions = f"{img.width}x{img.height}"
        except:
            pass
            
    # Calculate SHA256
    sha256 = ""
    try:
        with open(file_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()
    except:
        pass
        
    return {
        "size_bytes": size,
        "created_at": created,
        "dimensions": dimensions,
        "sha256": sha256
    }

def generate_manifest(target_root):
    logger.info("Generating assets manifest.json...")
    manifest = {
        "name": "PyFlare Branding manifest",
        "generated_at": datetime.datetime.now().isoformat(),
        "assets": {}
    }
    
    for root, dirs, files in os.walk(target_root):
        for file in files:
            if file == "manifest.json":
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, target_root).replace("\\", "/")
            
            meta = get_file_metadata(file_path)
            meta["category"] = rel_path.split("/")[0]
            manifest["assets"][rel_path] = meta
            
    with open(os.path.join(target_root, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
        
    logger.info("Successfully wrote manifest.json")
