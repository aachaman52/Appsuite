#!/usr/bin/env python3
import shutil
from pathlib import Path
import yaml
import sys

def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def clean(logger=None):
    config = load_config()
    import platform
    if platform.system() == "Linux" and "linux_work_dir" in config["build"]:
        work_dir = Path(config["build"]["linux_work_dir"])
    else:
        work_dir = Path(__file__).resolve().parent.parent / config["build"]["work_folder"]
    output_dir = Path(__file__).resolve().parent.parent / config["build"]["output_folder"]
    
    def log(msg):
        print(msg)
        if logger:
            logger.info(msg)
            
    log(f"Cleaning work directory: {work_dir}")
    if work_dir.exists():
        # Only remove extraction folders, keep the downloaded ISO if we want to save time next build
        extract_dir = work_dir / "iso_extracted"
        squashfs_dir = work_dir / "squashfs-root"
        
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
            log(f"  Removed {extract_dir}")
            
        if squashfs_dir.exists():
            shutil.rmtree(squashfs_dir)
            log(f"  Removed {squashfs_dir}")
            
    log(f"Cleaning output directory: {output_dir}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
        log(f"  Removed {output_dir}")
        
    output_dir.mkdir(parents=True, exist_ok=True)
    log("[OK] Clean complete.")

if __name__ == "__main__":
    import os
    if os.geteuid() != 0:
        print("[WARNING] You may need root privileges to clean squashfs-root if it contains root-owned files.")
    clean()
