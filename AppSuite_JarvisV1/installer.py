import os
import sys
import shutil
import json
import sqlite3
from pathlib import Path
import subprocess

def check_binary(name: str, config_path: str = None) -> bool:
    if config_path and Path(config_path).exists():
        return True
    path = shutil.which(name)
    if path:
        return True
    return False

def check_python_version():
    v = sys.version_info
    return v.major >= 3 and v.minor >= 10

def detect_cuda() -> bool:
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False

def detect_msvc() -> bool:
    # Basic check for cl.exe in path
    return check_binary("cl")

def auto_scan_binary(name: str, search_dirs: list[Path]) -> str:
    """Scans common directories for a binary if not in PATH."""
    for sdir in search_dirs:
        if not sdir.exists(): continue
        for root, dirs, files in os.walk(sdir):
            for f in files:
                if name.lower() in f.lower() and f.endswith(".exe"):
                    return str(Path(root) / f)
    return ""

def detect_ffmpeg() -> bool:
    return check_binary("ffmpeg")

def main():
    print("========================================")
    print("      AppSuite V1 First-Run Wizard      ")
    print("========================================")
    
    # 1. Generate Folders
    folders = ["config", "data", "output", "crash_reports"]
    for f in folders:
        Path(f).mkdir(parents=True, exist_ok=True)
    
    # 2. Config Create
    config_file = Path("config/default_config.yaml")
    if not config_file.exists():
        print("Creating default config...")
        # Write basic config if missing

    # 3. Initialize DB
    db_path = Path("data/appsuite.db")
    print("Initializing Database...")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.close()
    except Exception as e:
        print(f"[ERROR] Database creation failed: {e}")
        return
        
    # 4. Prompt for API Keys
    print("\n[Configuration] API Keys")
    print("AppSuite uses LLMs for generation. Please provide at least one API Key.")
    providers = []
    
    anthropic_key = input("  Anthropic API Key (leave blank to skip): ").strip()
    if anthropic_key:
        providers.append({"id": "anthropic", "priority": 1, "model": "claude-3-7-sonnet-20250219", "api_key": anthropic_key})
        
    openai_key = input("  OpenAI API Key (leave blank to skip): ").strip()
    if openai_key:
        providers.append({"id": "openai", "priority": 2, "model": "gpt-4o", "api_key": openai_key})
        
    if providers:
        providers_file = Path("config/providers.json")
        with open(providers_file, "w") as f:
            json.dump({"providers": providers}, f, indent=4)
        print("  [OK] Providers configured.")
    else:
        print("  [WARNING] No API keys provided. LLM generations will fallback to local rules.")

    # 5. Check Dependencies
    
    godot_passed = check_binary("godot")
    if not godot_passed:
        print("  Godot not in PATH. Scanning C:\\Program Files...")
        godot_path = auto_scan_binary("godot", [Path("C:/Program Files/Godot"), Path("C:/Program Files")])
        if godot_path:
            print(f"  [OK] Auto-detected Godot at {godot_path}")
            godot_passed = True
        else:
            print("  [WARNING] Godot not found.")
            
    blender_passed = check_binary("blender")
    if not blender_passed:
        print("  Blender not in PATH. Scanning C:\\Program Files...")
        blender_path = auto_scan_binary("blender", [Path("C:/Program Files/Blender Foundation"), Path("C:/Program Files")])
        if blender_path:
            print(f"  [OK] Auto-detected Blender at {blender_path}")
            blender_passed = True
        else:
            print("  [WARNING] Blender not found.")

    report = {
        "Python": "Passed" if check_python_version() else "Failed",
        "Git": "Passed" if check_binary("git") else "Failed",
        "Godot": "Passed" if godot_passed else "Warning (Missing)",
        "Blender": "Passed" if blender_passed else "Warning (Missing)",
        "CUDA": "Passed" if detect_cuda() else "Warning (CPU Only)",
        "MSVC": "Passed" if detect_msvc() else "Warning (No C++ Compilation)",
        "FFmpeg": "Passed" if detect_ffmpeg() else "Warning (No Media Processing)"
    }
    
    print("\nDependency Check Results:")
    for k, v in report.items():
        print(f"  {k}: {v}")
        
    report_path = Path("output/installation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
        
    print(f"\nInstallation complete! Report saved to {report_path}")

if __name__ == "__main__":
    main()
