#!/usr/bin/env python3
"""
AppSuite OS Build Orchestrator
------------------------------
This script automates the creation of the AppSuite OS bootable ISO.
It requires root privileges and a Debian/Ubuntu host environment.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
BUILD_DIR = BASE_DIR / "build"
SCRIPTS_DIR = BASE_DIR / "scripts"
CONFIG_FILE = BASE_DIR / "config" / "settings.yaml"

def check_root():
    if os.geteuid() != 0:
        print("This script must be run as root (sudo).")
        sys.exit(1)

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)

def run_script(script_name: str, env: dict = None):
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"Error: Script {script_name} not found!")
        sys.exit(1)
        
    print(f"\n[BUILD] === Running {script_name} ===")
    
    # Make executable
    os.chmod(script_path, 0o755)
    
    script_env = os.environ.copy()
    if env:
        script_env.update(env)
        
    try:
        subprocess.run([str(script_path)], env=script_env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] {script_name} failed with exit code {e.returncode}")
        sys.exit(1)

def main():
    print("========================================")
    print("      AppSuite OS ISO Builder           ")
    print("========================================")
    
    check_root()
    
    if not BUILD_DIR.exists():
        BUILD_DIR.mkdir()
        
    config = load_config()
    
    env_vars = {
        "BASE_ISO_URL": config["os"]["base_url"],
        "ISO_LABEL": config["os"]["iso_label"],
        "BASE_DIR": str(BASE_DIR),
        "BUILD_DIR": str(BUILD_DIR)
    }
    
    run_script("fetch_base_iso.sh", env_vars)
    run_script("extract_iso.sh", env_vars)
    run_script("chroot_env.sh", env_vars)
    run_script("generate_iso.sh", env_vars)
    
    print("\n[SUCCESS] Build complete! Check the build/ directory for the output ISO.")

if __name__ == "__main__":
    main()
