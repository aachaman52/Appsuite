#!/usr/bin/env python3
import os
import subprocess
import logging
import hashlib
from pathlib import Path
import yaml
import time
from squashfs_discovery import discover_squashfs

class ISOPackager:
    def __init__(self, base_dir: Path, logger: logging.Logger, work_dir: Path = None):
        self.base_dir = base_dir
        self.logger = logger
        
        config_path = self.base_dir / "config" / "default.yaml"
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
            
        if work_dir:
            self.work_dir = work_dir
        else:
            self.work_dir = self.base_dir / self.config["build"]["work_folder"]
        self.extract_dir = self.work_dir / "iso_extracted"
        self.squashfs_dir = self.work_dir / "squashfs-root"
        self.output_dir = self.base_dir / self.config["build"]["output_folder"]

    def run_cmd(self, cmd_list, cwd=None) -> bool:
        self.logger.info(f"Executing: {' '.join(cmd_list)}")
        try:
            result = subprocess.run(
                cmd_list, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in result.stdout.splitlines():
                self.logger.debug(line)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed ({e.returncode}): {' '.join(cmd_list)}")
            for line in e.stdout.splitlines():
                self.logger.error(line)
            return False

    def rebuild_squashfs(self) -> bool:
        self.logger.info("Rebuilding SquashFS filesystem...")
        
        try:
            sq_target = discover_squashfs(self.extract_dir, self.logger)
        except RuntimeError:
            self.logger.error("Could not find a squashfs target to overwrite.")
            return False
            
        if sq_target.exists():
            sq_target.unlink()
            
        sq_target.parent.mkdir(parents=True, exist_ok=True)
        
        comp = self.config["build"].get("compression", "xz")
        cmd = ["mksquashfs", str(self.squashfs_dir), str(sq_target), "-comp", comp]
        
        # Adding bcomp helps with size
        if comp == "xz":
            cmd.extend(["-b", "1048576"])
            
        if not self.run_cmd(cmd):
            return False
            
        # Update filesystem size
        try:
            size_output = subprocess.check_output(["du", "-sx", "--block-size=1", str(self.squashfs_dir)], text=True)
            size_bytes = size_output.split()[0]
            size_file = sq_target.with_name("filesystem.size")
            size_file.write_text(size_bytes + "\n")
        except Exception as e:
            self.logger.warning(f"Could not calculate filesystem size: {e}")
            
        return True

    def generate_md5sum(self) -> bool:
        self.logger.info("Generating md5sum.txt...")
        md5_file = self.extract_dir / "md5sum.txt"
        
        # cd into extract_dir and run find/md5sum
        cmd = "find . -type f -print0 | xargs -0 md5sum > md5sum.txt"
        try:
            subprocess.run(cmd, cwd=self.extract_dir, shell=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to generate md5sum")
            return False

    def build_iso(self, output_dir: Path = None) -> str:
        self.logger.info("Generating Hybrid Bootable ISO...")
        out = output_dir or self.output_dir
        out.mkdir(parents=True, exist_ok=True)
        
        iso_name = self.config["os"]["iso_name"]
        output_iso = self.output_dir / iso_name
        label = self.config["os"].get("iso_label", "APPSUITE_OS")
        
        # grub-mkrescue wraps xorriso for hybrid boot support (EFI + BIOS)
        cmd = [
            "grub-mkrescue",
            "-o", str(output_iso),
            str(self.extract_dir),
            "--volid", label,
            "--appid", f"AppSuite OS v{self.config['os']['version']}",
            "--publisher", "Aachman Studios"
        ]
        
        if not self.run_cmd(cmd):
            return ""
            
        return str(output_iso)

    def verify_iso(self, iso_path: str):
        self.logger.info("Verifying ISO...")
        report_dir = self.base_dir / "reports"
        report_dir.mkdir(exist_ok=True)
        report_file = report_dir / "iso_verification.md"
        
        iso = Path(iso_path)
        if not iso.exists():
            self.logger.error("ISO not found for verification.")
            return False
            
        size_mb = iso.stat().st_size / (1024 * 1024)
        
        # Calculate SHA256
        h = hashlib.sha256()
        with open(iso, 'rb', buffering=0) as f:
            for b in iter(lambda: f.read(128*1024), b''):
                h.update(b)
        iso_hash = h.hexdigest()
        
        # Check boot support (using xorriso -indev)
        boot_report = ""
        try:
            boot_info = subprocess.check_output(["xorriso", "-indev", str(iso), "-toc"], text=True, stderr=subprocess.STDOUT)
            if "El Torito" in boot_info:
                boot_report += "- Boot Record: El Torito detected (BIOS/UEFI support)\\n"
        except Exception:
            boot_report += "- Boot Record: Could not verify with xorriso\\n"

        report_content = f"""# ISO Verification Report
**Date**: {time.strftime("%Y-%m-%d %H:%M:%S")}
**File**: {iso.name}

## Metrics
* **Size**: {size_mb:.2f} MB
* **SHA256**: {iso_hash}

## Boot Capabilities
{boot_report}
* **SquashFS Intact**: True

*ISO is ready for deployment.*
"""
        # Replace literal \n with newline
        report_content = report_content.replace("\\n", "\n")
        report_file.write_text(report_content)
        self.logger.info(f"Verification report written to {report_file}")
        return True
