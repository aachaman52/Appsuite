#!/usr/bin/env python3
import shutil
import sys

REQUIRED_CMDS = [
    ("python3", "sudo apt install python3"),
    ("git", "sudo apt install git"),
    ("xorriso", "sudo apt install xorriso"),
    ("mksquashfs", "sudo apt install squashfs-tools"),
    ("unsquashfs", "sudo apt install squashfs-tools"),
    ("rsync", "sudo apt install rsync"),
    ("grub-mkrescue", "sudo apt install grub-common grub-pc-bin grub-efi-amd64-bin"),
    ("mformat", "sudo apt install mtools")
]

def verify_dependencies():
    missing = []
    print("Verifying build dependencies...")
    for cmd, install_cmd in REQUIRED_CMDS:
        if shutil.which(cmd) is None:
            missing.append((cmd, install_cmd))
            print(f"  [MISSING] {cmd}")
        else:
            print(f"  [OK] {cmd}")
            
    if missing:
        print("\n[ERROR] Missing required dependencies.")
        print("Please install them using the following commands:\n")
        for cmd, install_cmd in missing:
            print(f"  {install_cmd}")
        sys.exit(1)
    
    print("\n[SUCCESS] All dependencies are satisfied.")

if __name__ == "__main__":
    verify_dependencies()
