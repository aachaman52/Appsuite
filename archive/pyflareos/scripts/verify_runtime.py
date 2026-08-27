#!/usr/bin/env python3
"""
PyFlare OS — Automated Runtime Verification
-------------------------------------------
This script boots the generated ISO using QEMU and uses serial output
to verify the boot process, kernel initialization, systemd targets, 
and NetworkManager startup.

Status: Pending Linux Execution (QEMU with KVM is recommended).
"""

import sys
import time
import platform
import subprocess
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
REPORT_DIR = ROOT / "reports"

def verify_runtime():
    print("===========================================================")
    print("   PyFlare OS — Automated Runtime Verification             ")
    print("===========================================================")

    if platform.system() == "Windows":
        print("[SKIP] Runtime verification requires a Linux host with QEMU/KVM.")
        print("[INFO] Status: Pending Linux Execution")
        
        # Output a dummy report for Windows
        report = {
            "status": "PENDING_LINUX_EXECUTION",
            "reason": "Host is Windows, cannot spawn QEMU/KVM optimally for Linux ISO.",
            "tests": {
                "grub_boot": "PENDING",
                "kernel_load": "PENDING",
                "systemd_init": "PENDING",
                "gdm_start": "PENDING",
                "network_manager": "PENDING"
            }
        }
        with open(REPORT_DIR / "runtime_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return 0

    iso_path = OUTPUT_DIR / "pyflare-os-1.0.0-ember-amd64.iso"
    if not iso_path.exists():
        print(f"[FATAL] ISO not found at {iso_path}")
        return 1

    print(f"[INFO] Booting ISO in QEMU: {iso_path.name}")
    
    # Run QEMU headlessly and pipe serial output to a log
    qemu_cmd = [
        "qemu-system-x86_64",
        "-enable-kvm",
        "-m", "4096",
        "-smp", "2",
        "-cdrom", str(iso_path),
        "-nographic",
        "-serial", "file:/tmp/pyflare_boot.log",
        "-boot", "d"
    ]

    try:
        proc = subprocess.Popen(qemu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("[INFO] Waiting for system to boot (timeout 120s)...")
        time.sleep(120)
        
        proc.terminate()
        
        # Analyze the serial log for success markers
        boot_log = Path("/tmp/pyflare_boot.log")
        log_content = boot_log.read_text(errors="ignore") if boot_log.exists() else ""

        tests = {
            "kernel_load": "Linux version" in log_content,
            "systemd_init": "Welcome to Ubuntu" in log_content or "Reached target" in log_content,
            "network_manager": "NetworkManager" in log_content,
            "no_kernel_panic": "Kernel panic" not in log_content,
            "no_boot_loop": "Restarting system" not in log_content
        }

        success = all(tests.values())
        print(f"[RESULT] Verification {'SUCCESS' if success else 'FAILED'}")
        
        report = {
            "status": "SUCCESS" if success else "FAILED",
            "tests": tests,
            "boot_log_size_bytes": len(log_content)
        }
        with open(REPORT_DIR / "runtime_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return 0 if success else 1
        
    except Exception as e:
        print(f"[FATAL] QEMU execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(verify_runtime())
