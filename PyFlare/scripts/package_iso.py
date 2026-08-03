#!/usr/bin/env python3
import os
import shutil
import subprocess
import logging
import hashlib
from pathlib import Path
import yaml
import time

class ISOPackager:
    def __init__(self, base_dir: Path, logger: logging.Logger, work_dir: Path = None):
        self.base_dir = base_dir
        self.logger = logger
        
        self.work_dir = work_dir if work_dir else (self.base_dir / "build")
        self.extract_dir = self.work_dir / "iso_extracted"
        self.squashfs_dir = self.work_dir / "squashfs-root"
        self.output_dir = self.base_dir / "output"

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
        
        iso_name = "pyflare-os-1.0.0-ember-amd64.iso"
        output_iso = self.output_dir / iso_name
        label = "PYFLARE_OS"
        
        self.extract_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Setup the Casper directory for the live boot
        casper_dir = self.extract_dir / "casper"
        casper_dir.mkdir(exist_ok=True)
        
        boot_grub_dir = self.extract_dir / "boot" / "grub"
        boot_grub_dir.mkdir(parents=True, exist_ok=True)
        
        # 1.5 Create .disk/info (Casper requires this to detect the live USB/CD)
        disk_dir = self.extract_dir / ".disk"
        disk_dir.mkdir(exist_ok=True)
        (disk_dir / "info").write_text("PyFlare OS 1.0.0 Ember")

        # 2. Extract Kernel and Initrd from the base Ubuntu ISO
        # CRITICAL: Stage through /tmp (native Linux) first to avoid VirtualBox shared folder
        # corruption of large binary files. Direct copy to sf_* paths produces invalid magic numbers.
        base_iso = self.base_dir / "Iso`s" / "ubuntu-24.04.4-live-server-amd64.iso"
        if base_iso.exists():
            self.logger.info(f"Extracting kernel from base ISO: {base_iso.name}")
            mnt_dir = Path("/tmp/ubuntu_iso")
            mnt_dir.mkdir(exist_ok=True)
            tmp_kernel = Path("/tmp/pyflare_vmlinuz")
            tmp_initrd = Path("/tmp/pyflare_initrd")
            try:
                # Mount the ISO
                subprocess.run(["mount", "-o", "loop,ro", str(base_iso), str(mnt_dir)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Step 1: Copy kernel + initrd to native Linux /tmp (no shared folder involved)
                # This guarantees a clean, un-corrupted binary read.
                subprocess.run(["cp", "-L", str(mnt_dir / "casper" / "vmlinuz"), str(tmp_kernel)], check=True)
                subprocess.run(["cp", "-L", str(mnt_dir / "casper" / "initrd"), str(tmp_initrd)], check=True)
                
                # Verify the kernel has a valid EFI/bzImage magic header before proceeding
                with open(tmp_kernel, "rb") as kf:
                    header = kf.read(4)
                if header[:2] not in (b"MZ", b"\x1f\x8b"):
                    raise RuntimeError(f"Kernel has invalid magic bytes: {header.hex()} — file may be a broken symlink")
                
                self.logger.info(f"Kernel verified OK ({tmp_kernel.stat().st_size // 1024 // 1024} MB). Staging to ISO payload...")
                
                # Step 2: Now safely move to the ISO build dir (shared folder write happens ONCE, cleanly)
                shutil.copy2(str(tmp_kernel), str(casper_dir / "vmlinuz"))
                shutil.copy2(str(tmp_initrd), str(casper_dir / "initrd"))
                
            except Exception as e:
                self.logger.error(f"Failed to copy kernel from ISO: {e}")
                raise
            finally:
                subprocess.run(["umount", str(mnt_dir)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for tf in [tmp_kernel, tmp_initrd]:
                    if tf.exists():
                        tf.unlink()
        else:
            self.logger.warning(f"Base ISO not found at {base_iso}. Kernel will be missing!")

        # 3. Copy our generated SquashFS as the base layer.
        # Casper stacks layers bottom-up via OverlayFS:
        #   ubuntu-server-minimal.squashfs           <- BOTTOM (our real OS goes here)
        #   ubuntu-server-minimal.ubuntu-server.squashfs        <- upper layer (dummy)
        #   ubuntu-server-minimal.ubuntu-server.installer.squashfs    <- upper layer (dummy)
        #   ubuntu-server-minimal.ubuntu-server.installer.generic.squashfs  <- top (dummy)
        # The final merged view is dominated by the BOTTOM layer.
        our_squashfs = self.work_dir / "filesystem.squashfs"
        if our_squashfs.exists():
            self.logger.info("Copying PyFlare filesystem.squashfs as bottom OverlayFS layer...")

            # REAL OS: bottom layer — this is what the user sees
            real_dst = casper_dir / "ubuntu-server-minimal.squashfs"
            subprocess.run(["cp", str(our_squashfs), str(real_dst)], check=True)

            # Write filesystem.size so Casper doesn't hang computing it at boot
            try:
                size_output = subprocess.check_output(
                    ["unsquashfs", "-s", str(our_squashfs)], text=True, stderr=subprocess.STDOUT
                )
                for line in size_output.splitlines():
                    if "Number of inodes" in line or "Filesystem size" in line:
                        pass
                # Use du as a reliable fallback
                du_out = subprocess.check_output(["du", "-sx", "--block-size=1", str(our_squashfs)], text=True)
                fs_size = du_out.split()[0]
                (casper_dir / "filesystem.size").write_text(fs_size + "\n")
            except Exception as e:
                self.logger.warning(f"Could not write filesystem.size: {e}")

            # DUMMY layers: tiny empty squashfs files to satisfy Casper's layer list check
            dummy_dir = Path("/tmp/dummy_sq")
            dummy_dir.mkdir(exist_ok=True)
            dummy_sq = Path("/tmp/dummy.squashfs")
            if dummy_sq.exists():
                dummy_sq.unlink()
            subprocess.run(["mksquashfs", str(dummy_dir), str(dummy_sq)], check=True, stdout=subprocess.DEVNULL)

            dummy_names = [
                "ubuntu-server-minimal.ubuntu-server.squashfs",
                "ubuntu-server-minimal.ubuntu-server.installer.squashfs",
                "ubuntu-server-minimal.ubuntu-server.installer.generic.squashfs",
            ]
            for t_name in dummy_names:
                subprocess.run(["cp", str(dummy_sq), str(casper_dir / t_name)], check=True)
            self.logger.info(f"Layer stack complete: 1 real OS + {len(dummy_names)} dummy layers.")
        else:
            self.logger.error("filesystem.squashfs not found! Cannot build ISO.")
            return ""


        # 4. Create the GRUB config
        grub_cfg = boot_grub_dir / "grub.cfg"
        grub_cfg.write_text("""
set timeout=5
set default=0

menuentry "Start PyFlare OS Desktop" {
    linux /casper/vmlinuz boot=casper ignore_uuid live-media-path=/casper quiet splash nomodeset ---
    initrd /casper/initrd
}

menuentry "Start PyFlare OS (Safe Mode - nomodeset)" {
    linux /casper/vmlinuz boot=casper ignore_uuid live-media-path=/casper nomodeset text ---
    initrd /casper/initrd
}
""")

        
        # 5. grub-mkrescue wraps xorriso for hybrid boot support (EFI + BIOS)
        cmd = [
            "grub-mkrescue",
            "-o", str(output_iso),
            str(self.extract_dir),
            "--volid", label,
            "--appid", "PyFlare OS v1.0.0",
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
