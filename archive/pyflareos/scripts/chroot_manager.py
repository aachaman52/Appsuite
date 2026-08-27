#!/usr/bin/env python3
import os
import subprocess
import logging
from pathlib import Path

class ChrootManager:
    """Safely manages mounting and unmounting virtual filesystems for chroot environments."""
    
    def __init__(self, rootfs_path: Path, logger: logging.Logger):
        self.rootfs = rootfs_path
        self.logger = logger
        self.mounts = [
            ("/proc", "proc", "proc", []),
            ("/sys", "sysfs", "sysfs", []),
            ("/dev", None, None, ["--bind", "/dev"]),
            ("/dev/pts", "devpts", "devpts", []),
            ("/run", None, None, ["--bind", "/run"]),
        ]
        
    def __enter__(self):
        self.logger.info(f"Setting up chroot environment at {self.rootfs}")
        
        # Copy DNS resolution so we have internet inside chroot
        resolv_conf = Path("/etc/resolv.conf")
        target_resolv = self.rootfs / "etc/resolv.conf"
        if resolv_conf.exists():
            target_resolv.unlink(missing_ok=True)
            try:
                import shutil
                shutil.copy2(resolv_conf, target_resolv)
            except Exception as e:
                self.logger.warning(f"Could not copy resolv.conf: {e}")

        # Mount virtual filesystems
        for mnt_point, fstype, src, extras in self.mounts:
            target = str(self.rootfs) + mnt_point
            os.makedirs(target, exist_ok=True)
            cmd = ["mount"] + extras
            if fstype:
                cmd += ["-t", fstype]
            if src:
                cmd += [src]
            cmd += [target]
            
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.logger.debug(f"Mounted {mnt_point}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to mount {mnt_point}: {e}")

        return self

    def run(self, command: str, env: dict = None) -> bool:
        """Run a command safely inside the chroot."""
        self.logger.info(f"Chroot executing: {command}")
        cmd = ["chroot", str(self.rootfs), "/bin/bash", "-c", command]
        
        script_env = os.environ.copy()
        script_env["DEBIAN_FRONTEND"] = "noninteractive"
        script_env["LC_ALL"] = "C"
        if env:
            script_env.update(env)
            
        try:
            result = subprocess.run(
                cmd,
                env=script_env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in result.stdout.splitlines():
                self.logger.debug(line)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Chroot command failed with exit code {e.returncode}: {command}")
            for line in e.stdout.splitlines():
                self.logger.error(line)
            return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info(f"Tearing down chroot environment at {self.rootfs}")
        # Unmount in reverse order
        for mnt_point, _, _, _ in reversed(self.mounts):
            target = str(self.rootfs) + mnt_point
            try:
                # Use lazy unmount to detach immediately
                subprocess.run(["umount", "-lf", target], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.logger.debug(f"Unmounted {mnt_point}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to unmount {target}: {e}")
                
        # Clean up resolv.conf
        target_resolv = self.rootfs / "etc/resolv.conf"
        target_resolv.unlink(missing_ok=True)
        # Create a symlink back to standard systemd-resolved
        try:
            target_resolv.symlink_to("../run/systemd/resolve/stub-resolv.conf")
        except Exception:
            pass
            
        if exc_type:
            self.logger.error(f"Chroot exited with error: {exc_val}")
