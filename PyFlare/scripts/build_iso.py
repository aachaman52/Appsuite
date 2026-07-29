#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
from pathlib import Path
import yaml

from verify_dependencies import verify_dependencies
from download_base import download_base
from clean import clean
from chroot_manager import ChrootManager
from package_installer import PackageInstaller
from branding import BrandingEngine
from package_iso import ISOPackager
from squashfs_discovery import discover_squashfs
import time

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "config" / "default.yaml"

def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger("AppSuiteOS_Builder")
    logger.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Build log (INFO and up)
    fh = logging.FileHandler(LOG_DIR / "build.log", mode='w')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Error log (ERROR and up)
    eh = logging.FileHandler(LOG_DIR / "errors.log", mode='w')
    eh.setLevel(logging.ERROR)
    eh.setFormatter(formatter)
    logger.addHandler(eh)
    
    # Console (INFO and up)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(ch)
    
    return logger

def run_command(cmd_list, logger, cwd=None, warn_exit_codes=()):
    logger.info(f"Running command: {' '.join(cmd_list)}")
    try:
        result = subprocess.run(
            cmd_list,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        for line in result.stdout.splitlines():
            logger.debug(line)
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode in warn_exit_codes:
            logger.warning(f"Command returned exit code {e.returncode} (non-fatal): {' '.join(cmd_list)}")
            for line in e.stdout.splitlines():
                logger.warning(line)
            return True
        logger.error(f"Command failed with exit code {e.returncode}: {' '.join(cmd_list)}")
        for line in e.stdout.splitlines():
            logger.error(line)
        return False

def detect_iso_layout(extract_dir: Path, logger) -> dict:
    """
    Detects the ISO directory layout by inspecting what directories actually exist.
    Returns a dict with detected paths so no downstream code hardcodes them.
    """
    layout = {
        "casper_dir": None,
        "boot_dir": None,
        "efi_dir": None,
        "grub_dir": None,
    }

    # Locate live filesystem dir — could be casper/ (Ubuntu) or live/ (Debian)
    for name in ["casper", "live", "install"]:
        candidate = extract_dir / name
        if candidate.exists() and any(candidate.rglob("*.squashfs")):
            layout["casper_dir"] = candidate
            logger.info(f"[OK] Live filesystem directory: {name}/")
            break

    if not layout["casper_dir"]:
        logger.warning("Could not detect live filesystem directory — squashfs discovery will scan all directories.")

    # Detect boot directory
    for name in ["boot", "isolinux", "syslinux"]:
        candidate = extract_dir / name
        if candidate.exists():
            layout["boot_dir"] = candidate
            logger.info(f"[OK] Boot directory: {name}/")
            break

    # Detect EFI
    for name in ["EFI", "efi"]:
        candidate = extract_dir / name
        if candidate.exists():
            layout["efi_dir"] = candidate
            logger.info(f"[OK] EFI directory: {name}/")
            break

    # Detect GRUB
    for grub_path in [extract_dir / "boot" / "grub", extract_dir / "grub"]:
        if grub_path.exists():
            layout["grub_dir"] = grub_path
            logger.info(f"[OK] GRUB directory: {grub_path.relative_to(extract_dir)}")
            break

    return layout


def extract_iso(iso_path: Path, work_dir: Path, logger):
    logger.info("Extracting ISO...")
    extract_dir = work_dir / "iso_extracted"
    squashfs_dir = work_dir / "squashfs-root"

    extract_dir.mkdir(parents=True, exist_ok=True)

    # Mount ISO
    mnt_dir = work_dir / "mnt"
    mnt_dir.mkdir(exist_ok=True)

    if not run_command(["mount", "-o", "loop", str(iso_path), str(mnt_dir)], logger):
        sys.exit(1)

    logger.info("Copying ISO contents (this may take a minute)...")
    if not run_command(["rsync", "-a", f"{mnt_dir}/", str(extract_dir)], logger):
        run_command(["umount", str(mnt_dir)], logger)
        sys.exit(1)

    run_command(["umount", str(mnt_dir)], logger)
    try:
        mnt_dir.rmdir()
    except OSError:
        pass

    logger.info("Detecting ISO layout...")
    layout = detect_iso_layout(extract_dir, logger)

    logger.info("Discovering root squashfs layers...")
    all_squashfs = list((extract_dir / "casper").rglob("*.squashfs"))
    if not all_squashfs and (extract_dir / "install").exists():
        all_squashfs = list((extract_dir / "install").rglob("*.squashfs"))

    from squashfs_discovery import _score
    # Build ordered list: base layer first (highest score number = most generic = base)
    # Then overlay layers in decreasing score (most specific on top)
    non_installer = sorted(
        [f for f in all_squashfs if "installer" not in f.name.lower()],
        key=lambda f: _score(f)[0],
        reverse=True  # highest score = most generic base, extracted first
    )

    if not non_installer:
        logger.error("No valid (non-installer) squashfs layers found.")
        sys.exit(1)

    logger.info(f"Extracting {len(non_installer)} squashfs layer(s) in order:")
    for f in non_installer:
        logger.info(f"  {f.name}")

    squashfs_dir.mkdir(parents=True, exist_ok=True)

    for sq in non_installer:
        tmp_layer = work_dir / f"_layer_{sq.stem}"
        # Always remove stale temp dir so unsquashfs starts clean
        import shutil as _shutil
        if tmp_layer.exists():
            logger.info(f"Removing stale layer dir: {tmp_layer.name}")
            _shutil.rmtree(str(tmp_layer))
        logger.info(f"Unsquashing layer: {sq.name}")
        if not run_command(["unsquashfs", "-d", str(tmp_layer), str(sq)], logger):
            sys.exit(1)
        # Overlay this layer onto squashfs_dir.
        # Use --update so overlay files replace base files but no deletions occur.
        # Exit code 23 = partial transfer (e.g. __pycache__ dir/file conflicts) — non-fatal.
        logger.info(f"Merging layer: {sq.name} -> squashfs-root/")
        if not run_command(["rsync", "-aHAX", "--update", f"{tmp_layer}/", f"{squashfs_dir}/"], logger,
                           warn_exit_codes=(23,)):
            sys.exit(1)
        # Clean up tmp layer
        import shutil as _shutil
        _shutil.rmtree(str(tmp_layer), ignore_errors=True)

    logger.info("[OK] ISO extracted successfully.")
    return layout

def customize_boot_config(extract_dir: Path, username: str, logger):
    logger.info("Customizing boot parameters for Live session...")
    grub_cfg = extract_dir / "boot" / "grub" / "grub.cfg"
    loopback_cfg = extract_dir / "boot" / "grub" / "loopback.cfg"
    
    grub_content = f"""set timeout=30

loadfont unicode

set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry "AppSuite OS Live Desktop" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper username={username} quiet splash ---
	initrd	/casper/initrd
}}
menuentry "AppSuite OS Live Desktop (Safe Graphics)" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper username={username} nomodeset quiet splash ---
	initrd	/casper/initrd
}}
menuentry "Ubuntu Server Installer (Original)" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz  ---
	initrd	/casper/initrd
}}
grub_platform
if [ "$grub_platform" = "efi" ]; then
menuentry 'Boot from next volume' {{
	exit 1
}}
menuentry 'UEFI Firmware Settings' {{
	fwsetup
}}
else
menuentry 'Test memory' {{
	linux16 /boot/memtest86+x64.bin
}}
fi
"""

    loopback_content = f"""menuentry "AppSuite OS Live Desktop" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper username={username} quiet splash iso-scan/filename=${{iso_path}} ---
	initrd	/casper/initrd
}}
menuentry "AppSuite OS Live Desktop (Safe Graphics)" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz boot=casper username={username} nomodeset quiet splash iso-scan/filename=${{iso_path}} ---
	initrd	/casper/initrd
}}
menuentry "Ubuntu Server Installer (Original)" {{
	set gfxpayload=keep
	linux	/casper/vmlinuz  iso-scan/filename=${{iso_path}} ---
	initrd	/casper/initrd
}}
"""

    if grub_cfg.exists():
        grub_cfg.parent.mkdir(parents=True, exist_ok=True)
        grub_cfg.write_text(grub_content)
        logger.info(f"  [OK] Customized {grub_cfg}")
        
    if loopback_cfg.exists():
        loopback_cfg.parent.mkdir(parents=True, exist_ok=True)
        loopback_cfg.write_text(loopback_content)
        logger.info(f"  [OK] Customized {loopback_cfg}")

def main():
    if os.geteuid() != 0:
        print("[ERROR] This script must be run as root (sudo).")
        sys.exit(1)
        
    logger = setup_logging()
    logger.info("========================================")
    logger.info("   AppSuite OS ISO Builder Phase 2      ")
    logger.info("========================================")
    
    with open(CONFIG_FILE, "r") as f:
        config = yaml.safe_load(f)
        
    # On Linux/WSL, use a native Linux filesystem path to support
    # unsquashfs device nodes and hard links (NTFS does not support these).
    import platform
    if platform.system() == "Linux" and "linux_work_dir" in config["build"]:
        work_dir = Path(config["build"]["linux_work_dir"])
        logger.info(f"[WSL/Linux] Using native work dir: {work_dir}")
    else:
        work_dir = BASE_DIR / config["build"]["work_folder"]
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Windows-accessible output directory (always relative to project)
    win_output_dir = BASE_DIR / config["build"]["output_folder"]
    win_output_dir.mkdir(parents=True, exist_ok=True)
        
    logger.info("Step 1: Verifying dependencies...")
    verify_dependencies()
    
    logger.info("\nStep 2: Cleaning previous builds...")
    clean(logger)
    
    logger.info("\nStep 3: Downloading base ISO...")
    iso_path = download_base(logger)
    
    logger.info("\nStep 4: Extracting ISO and preparing working directory...")
    extract_iso(iso_path, work_dir, logger)
    
    customize_boot_config(work_dir / "iso_extracted", config["system"]["username"], logger)
    
    logger.info("\nStep 5: Filesystem Customization (Chroot)...")
    squashfs_dir = work_dir / "squashfs-root"
    
    start_time = time.time()
    packages_yaml = BASE_DIR / "config" / "packages.yaml"
    with open(packages_yaml, "r") as pf:
        packages_config = yaml.safe_load(pf)
        
    with ChrootManager(squashfs_dir, logger) as chroot:
        installer = PackageInstaller(chroot, config, packages_config, logger)
        if not installer.configure_system():
            logger.error("Failed to configure system")
            sys.exit(1)
            
        if not installer.install_apt_packages():
            logger.error("Failed to install APT packages")
            sys.exit(1)
            
        if not installer.install_custom():
            logger.error("Failed to execute custom installs")
            sys.exit(1)
            
        if not installer.create_appsuite_integration():
            logger.error("Failed to integrate AppSuite /opt folder")
            sys.exit(1)
            
        branding = BrandingEngine(chroot, BASE_DIR, logger)
        if not branding.apply_branding():
            logger.error("Failed to apply branding")
            sys.exit(1)
            
        if not installer.cleanup():
            logger.warning("Filesystem cleanup failed, continuing anyway")
            
    chroot_duration = time.time() - start_time
    logger.info(f"Filesystem Customization completed in {chroot_duration:.2f} seconds")
    
    logger.info("\nStep 6: ISO Packaging and Verification...")
    start_time = time.time()
    packager = ISOPackager(BASE_DIR, logger, work_dir=work_dir)
    
    if not packager.rebuild_squashfs():
        logger.error("Failed to rebuild squashfs")
        sys.exit(1)
        
    if not packager.generate_md5sum():
        logger.warning("Failed to generate md5sum, continuing")
        
    final_iso = packager.build_iso(output_dir=work_dir / "output")
    if not final_iso:
        logger.error("Failed to generate final ISO")
        sys.exit(1)
        
    if not packager.verify_iso(final_iso):
        logger.error("ISO Verification failed")
        
    package_duration = time.time() - start_time
    logger.info(f"ISO Packaging completed in {package_duration:.2f} seconds")

    # Copy final ISO to the Windows-accessible output directory
    import shutil
    iso_dest = win_output_dir / Path(final_iso).name
    if Path(final_iso) != iso_dest:
        logger.info(f"Copying ISO to Windows output: {iso_dest}")
        shutil.copy2(final_iso, iso_dest)

    logger.info("\n========================================")
    logger.info("[SUCCESS] Pipeline Phase 3 completed.")
    logger.info(f"Final Bootable ISO ready at: {iso_dest}")

if __name__ == "__main__":
    main()
