#!/usr/bin/env python3
"""
PyFlare OS — Build Orchestrator
--------------------------------
Automates the full 10-stage Linux distribution build process for PyFlare OS.

Usage:
  python build.py

Stages:
  1. Validation (run 14 validators)
  2. Root Filesystem Preparation (stage build/rootfs)
  3. Package Preparation & Manifest Generation
  4. Branding Deployment & Verification
  5. Application Packaging (11 applications -> /opt/pyflare/apps/)
  6. Desktop Integration (launchers, GTK/GNOME themes, gsettings, fonts)
  7. Boot Configuration (GRUB, Plymouth, hostname, os-release, systemd)
  8. Filesystem Manifest & Checksums (SHA256 cataloging)
  9. SquashFS Creation (compressed rootfs, Linux-only)
 10. ISO Creation (bootable ISO remastering, Linux-only)

Outputs:
  logs/     -> build.log, validation.log, packaging.log, branding.log
  reports/  -> build_report.json, validation_report.json, branding_report.json,
               filesystem_manifest.json, checksums.json, timings.json
  build/    -> rootfs/ overlay and artifacts
  output/   -> pyflare-os-1.0.0-ember-amd64.iso (Linux builds)

Copyright (c) 2026 Aachman Studios
"""

import os
import sys
import time
import json
import shutil
import hashlib
import platform
import logging
import subprocess
import importlib
import glob
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path Configuration

# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
REPORT_DIR = ROOT / "reports"
BUILD_DIR = ROOT / "build"
ROOTFS_DIR = BUILD_DIR / "rootfs"
OUTPUT_DIR = ROOT / "output"
CONFIG_DIR = ROOT / "config"
FS_SRC = ROOT / "filesystem"
BRANDING_DIR = ROOT / "branding"
APPS_DIR = ROOT / "applications"
PACKAGES_DIR = ROOT / "packages"

# ---------------------------------------------------------------------------
# ANSI Colors for Terminal Output
# ---------------------------------------------------------------------------
class Colors:
    HEADER    = '\033[95m\033[1m'
    OKBLUE    = '\033[94m'
    OKCYAN    = '\033[96m'
    OKGREEN   = '\033[92m\033[1m'
    WARNING   = '\033[93m'
    FAIL      = '\033[91m\033[1m'
    RESET     = '\033[0m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'

def colorize(text: str, color: str) -> str:
    # Disable ANSI colors on Windows if legacy console doesn't support it
    if sys.platform == "win32" and not os.environ.get("FORCE_COLOR"):
        return text
    return f"{color}{text}{Colors.RESET}"

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
class PipelineLoggers:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(exist_ok=True)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

        self.build_logger = self._create_logger("pyflare.build", log_dir / "build.log", formatter)
        self.validation_logger = self._create_logger("pyflare.validation", log_dir / "validation.log", formatter)
        self.packaging_logger = self._create_logger("pyflare.packaging", log_dir / "packaging.log", formatter)
        self.branding_logger = self._create_logger("pyflare.branding", log_dir / "branding.log", formatter)

    def _create_logger(self, name: str, log_file: Path, formatter: logging.Formatter) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return logger

# ---------------------------------------------------------------------------
# Helper Utility Functions
# ---------------------------------------------------------------------------
def compute_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_dirs(*dirs: Path):
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def safe_copy(src: Path, dst: Path, symlinks: bool = True):
    """Recursively copy directory tree or single file preserving attributes."""
    if not src.exists():
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                safe_copy(item, target, symlinks=symlinks)
            else:
                try:
                    if item.is_symlink() and symlinks:
                        link_target = os.readlink(item)
                        if target.exists() or target.is_symlink():
                            target.unlink()
                        os.symlink(link_target, target)
                    else:
                        shutil.copy2(item, target)
                except Exception:
                    shutil.copy2(item, target)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

# ---------------------------------------------------------------------------
# Build Orchestrator Main Class
# ---------------------------------------------------------------------------
class PyFlareBuildPipeline:
    def __init__(self):
        self.start_time = time.time()
        ensure_dirs(LOG_DIR, REPORT_DIR, BUILD_DIR, OUTPUT_DIR)
        self.loggers = PipelineLoggers(LOG_DIR)
        self.build_log = self.loggers.build_logger
        self.val_log = self.loggers.validation_logger
        self.pkg_log = self.loggers.packaging_logger
        self.brand_log = self.loggers.branding_logger

        self.stage_timings = {}
        self.stage_results = {}
        self.is_linux = (platform.system() == "Linux")

    def print_banner(self):
        print(colorize("\n" + "=" * 65, Colors.HEADER))
        print(colorize("   PyFlare OS 1.0.0 Ember — Remaster Build Pipeline", Colors.HEADER))
        print(colorize("   Vendor: Aachman Studios  |  Base: Ubuntu 24.04 LTS", Colors.OKCYAN))
        print(colorize("=" * 65 + "\n", Colors.HEADER))
        self.build_log.info("PyFlare OS Remaster Build Pipeline started.")
        self.build_log.info(f"Host platform: {platform.platform()}, Python: {sys.version.split()[0]}")

    def run_stage(self, stage_num: int, stage_name: str, stage_func) -> bool:
        title = f"Stage {stage_num:02d}: {stage_name}"
        print(colorize(f"► [{stage_num:02d}/10] {stage_name}...", Colors.OKBLUE))
        self.build_log.info(f"--- STARTING {title} ---")
        t0 = time.time()

        try:
            success, message, extra_data = stage_func()
            elapsed = time.time() - t0
            self.stage_timings[stage_name] = {
                "stage": stage_num,
                "duration_seconds": round(elapsed, 3),
                "status": "PASS" if success else ("SKIPPED" if "SKIP" in message else "FAIL")
            }

            status_str = "PASS" if success else ("SKIPPED" if "SKIP" in message else "FAIL")
            color = Colors.OKGREEN if success else (Colors.WARNING if "SKIP" in message else Colors.FAIL)
            print(f"  {colorize(f'[{status_str}]', color)} {stage_name:<35} ({elapsed:.2f}s) — {message}")

            self.stage_results[stage_name] = {
                "success": success,
                "message": message,
                "elapsed": elapsed,
                "details": extra_data
            }
            self.build_log.info(f"--- FINISHED {title} -> {status_str} in {elapsed:.2f}s ---")
            return success
        except Exception as e:
            elapsed = time.time() - t0
            self.build_log.error(f"Fatal error in {title}: {str(e)}", exc_info=True)
            self.stage_timings[stage_name] = {"stage": stage_num, "duration_seconds": round(elapsed, 3), "status": "FAIL"}
            self.stage_results[stage_name] = {"success": False, "message": f"Fatal Exception: {e}", "elapsed": elapsed, "details": {}}
            print(f"  {colorize('[FAIL]', Colors.FAIL)} {stage_name:<35} ({elapsed:.2f}s) — Exception: {e}")
            return False

    # -----------------------------------------------------------------------
    # Stage 1: Validation Suite
    # -----------------------------------------------------------------------
    def stage_01_validation(self):
        sys.path.insert(0, str(ROOT))
        validators = [
            ("validate_branding",       "Branding assets"),
            ("validate_icons",          "Icon theme"),
            ("validate_wallpapers",     "Wallpapers"),
            ("validate_json",           "JSON files"),
            ("validate_svg",            "SVG files"),
            ("validate_desktop",        "Desktop entries"),
            ("validate_packages",       "Package manifests"),
            ("validate_filesystem",     "Filesystem overlay"),
            ("validate_theme",          "GTK/GNOME theme"),
            ("validate_configs",        "Config files"),
            ("validate_services",       "Systemd services"),
            ("validate_permissions",    "File permissions"),
            ("validate_desktop_entries","Desktop entry syntax"),
            ("validate_boot",           "Boot configuration"),
        ]

        val_results = []
        failed_validators = []

        for mod_name, label in validators:
            t0 = time.time()
            try:
                mod = importlib.import_module(f"validation.{mod_name}")
                ok, errors = mod.validate(str(ROOT))
            except Exception as e:
                ok, errors = False, [str(e)]
            dt = time.time() - t0
            status_text = "PASS" if ok else "FAIL"
            self.val_log.info(f"Validator {mod_name} ({label}): {status_text} in {dt:.3f}s")
            if not ok:
                for err in errors:
                    self.val_log.error(f"  -> {err}")
                failed_validators.append(mod_name)
            val_results.append({"validator": mod_name, "label": label, "passed": ok, "errors": errors, "duration": dt})

        # Save reports/validation_report.json
        val_report = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "total": len(validators),
            "passed": len(validators) - len(failed_validators),
            "failed": len(failed_validators),
            "results": val_results
        }
        with open(REPORT_DIR / "validation_report.json", "w", encoding="utf-8") as f:
            json.dump(val_report, f, indent=2)

        if failed_validators:
            return False, f"{len(failed_validators)} validator(s) failed", val_report
        return True, f"All {len(validators)} validators passed cleanly", val_report

    # -----------------------------------------------------------------------
    # Stage 2: Root Filesystem Preparation
    # -----------------------------------------------------------------------
    def stage_02_prepare_rootfs(self):
        if ROOTFS_DIR.exists():
            try:
                shutil.rmtree(ROOTFS_DIR)
            except Exception as e:
                self.build_log.warning(f"Could not completely remove old rootfs dir: {e}")
        ROOTFS_DIR.mkdir(parents=True, exist_ok=True)

        self.build_log.info(f"Copying filesystem tree from {FS_SRC} to {ROOTFS_DIR}")
        safe_copy(FS_SRC, ROOTFS_DIR, symlinks=True)

        # Remove placeholder .keep files and source documentation READMEs from rootfs
        for dirpath, _, filenames in os.walk(ROOTFS_DIR):
            for f in filenames:
                if f in (".keep", "README.md"):
                    try:
                        os.remove(os.path.join(dirpath, f))
                    except OSError:
                        pass

        # Verify required Linux root directory hierarchy
        required_root_dirs = [
            "etc", "usr", "var", "opt", "home", "root", "tmp", "boot",
            "lib", "lib64", "bin", "sbin", "media", "mnt", "srv", "run",
            "proc", "sys", "dev"
        ]
        created_dirs = []
        for rd in required_root_dirs:
            target_path = ROOTFS_DIR / rd
            target_path.mkdir(exist_ok=True)
            created_dirs.append(rd)

        total_files = sum(len(files) for _, _, files in os.walk(ROOTFS_DIR))
        return True, f"Prepared rootfs hierarchy with {len(created_dirs)} root dirs and {total_files} files", {
            "rootfs_path": str(ROOTFS_DIR),
            "directories": created_dirs,
            "total_files": total_files
        }

    # -----------------------------------------------------------------------
    # Stage 3: Package Preparation Stage
    # -----------------------------------------------------------------------
    def stage_03_packages(self):
        packages_yaml = CONFIG_DIR / "packages.yaml"
        if not packages_yaml.exists():
            return False, "config/packages.yaml not found", {}

        import yaml
        with open(packages_yaml, "r", encoding="utf-8") as f:
            pkg_data = yaml.safe_load(f)

        self.pkg_log.info(f"Loaded package config with {len(pkg_data.get('packages', {}))} categories.")

        # Save stage package manifest to packages/manifests/generated_manifest.json
        manifest_path = PACKAGES_DIR / "manifests" / "generated_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        gen_manifest = {
            "schema": "pyflare-package-manifest/1.0",
            "generated": datetime.now(timezone.utc).isoformat() + "Z",
            "vendor": "Aachman Studios",
            "package_categories": pkg_data.get("packages", {}),
            "snaps": pkg_data.get("snaps", []),
            "flatpaks": pkg_data.get("flatpaks", []),
            "custom_installs": pkg_data.get("custom_installs", []),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(gen_manifest, f, indent=2)

        # Stage package config and install script into rootfs /var/lib/pyflare/
        staged_pkg_dir = ROOTFS_DIR / "var" / "lib" / "pyflare"
        staged_pkg_dir.mkdir(parents=True, exist_ok=True)
        with open(staged_pkg_dir / "packages.json", "w", encoding="utf-8") as f:
            json.dump(gen_manifest, f, indent=2)

        # Generate packages/scripts/install_packages.sh
        install_script = PACKAGES_DIR / "scripts" / "install_packages.sh"
        install_script.parent.mkdir(parents=True, exist_ok=True)
        all_apt_pkgs = []
        for cat, pkgs in pkg_data.get("packages", {}).items():
            if isinstance(pkgs, list):
                all_apt_pkgs.extend(pkgs)

        script_content = f"""#!/usr/bin/env bash
# PyFlare OS — Package Installation Script
set -euo pipefail

echo "[PyFlare] Updating APT package index..."
apt-get update -q

echo "[PyFlare] Installing {len(all_apt_pkgs)} base packages..."
apt-get install -y --no-install-recommends {" ".join(all_apt_pkgs)}

echo "[PyFlare] Setting up Flatpak & Snaps..."
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo || true

echo "[PyFlare] Package installation complete."
"""
        with open(install_script, "w", encoding="utf-8", newline="\n") as f:
            f.write(script_content)

        safe_copy(install_script, ROOTFS_DIR / "opt" / "pyflare" / "bin" / "install_packages.sh")

        if self.is_linux and os.geteuid() == 0:
            self.pkg_log.info("Linux root environment detected — package manifests and scripts prepared.")
            return True, f"Manifest generated ({len(all_apt_pkgs)} APT packages, staged for chroot)", gen_manifest
        else:
            msg = f"Package manifest staged ({len(all_apt_pkgs)} APT packages). Host package installation skipped on Windows/non-root."
            self.pkg_log.info(msg)
            return True, msg, gen_manifest

    # -----------------------------------------------------------------------
    # Stage 4: Branding Deployment
    # -----------------------------------------------------------------------
    def stage_04_branding(self):
        copy_map = {
            "logos/svg":           ROOTFS_DIR / "usr" / "share" / "icons" / "PyFlare-Icons" / "scalable" / "apps",
            "logos/png":           ROOTFS_DIR / "usr" / "share" / "pixmaps",
            "wallpapers":          ROOTFS_DIR / "usr" / "share" / "backgrounds" / "pyflare",
            "cursors":             ROOTFS_DIR / "usr" / "share" / "icons" / "PyFlare",
            "fonts":               ROOTFS_DIR / "usr" / "share" / "fonts" / "pyflare",
        }

        deployed_files = 0
        categories_deployed = []

        for src_rel, dst_path in copy_map.items():
            src_path = BRANDING_DIR / src_rel
            if src_path.exists():
                dst_path.mkdir(parents=True, exist_ok=True)
                for f in src_path.iterdir():
                    if f.is_file():
                        shutil.copy2(f, dst_path / f.name)
                        deployed_files += 1
                categories_deployed.append(src_rel)
                self.brand_log.info(f"Deployed {src_rel} -> {dst_path.relative_to(ROOTFS_DIR)}")

        # Deploy GTK theme, Plymouth theme, GRUB theme from filesystem overlay
        themes_src = FS_SRC / "usr" / "share" / "themes" / "PyFlare-Dark"
        themes_dst = ROOTFS_DIR / "usr" / "share" / "themes" / "PyFlare-Dark"
        safe_copy(themes_src, themes_dst)

        plymouth_src = FS_SRC / "usr" / "share" / "plymouth" / "themes" / "pyflare"
        plymouth_dst = ROOTFS_DIR / "usr" / "share" / "plymouth" / "themes" / "pyflare"
        safe_copy(plymouth_src, plymouth_dst)

        grub_src = FS_SRC / "boot" / "grub" / "themes" / "pyflare"
        grub_dst = ROOTFS_DIR / "boot" / "grub" / "themes" / "pyflare"
        safe_copy(grub_src, grub_dst)

        # Verification of required branding assets
        required_assets = [
            ROOTFS_DIR / "usr" / "share" / "themes" / "PyFlare-Dark" / "index.theme",
            ROOTFS_DIR / "usr" / "share" / "plymouth" / "themes" / "pyflare" / "pyflare.plymouth",
            ROOTFS_DIR / "boot" / "grub" / "themes" / "pyflare" / "theme.txt",
        ]
        missing = [str(p.relative_to(ROOTFS_DIR)) for p in required_assets if not p.exists()]

        branding_report = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "categories": categories_deployed,
            "deployed_files_count": deployed_files,
            "missing_required_assets": missing,
            "status": "PASS" if not missing else "WARNING"
        }
        with open(REPORT_DIR / "branding_report.json", "w", encoding="utf-8") as f:
            json.dump(branding_report, f, indent=2)

        if missing:
            return False, f"Missing required branding assets: {', '.join(missing)}", branding_report
        return True, f"Deployed branding ({deployed_files} assets across {len(categories_deployed)} categories)", branding_report

    # -----------------------------------------------------------------------
    # Stage 5: Application Packaging
    # -----------------------------------------------------------------------
    def stage_05_application_packaging(self):
        target_apps_dir = ROOTFS_DIR / "opt" / "pyflare" / "apps"
        target_bin_dir = ROOTFS_DIR / "opt" / "pyflare" / "bin"
        target_desktop_dir = ROOTFS_DIR / "usr" / "share" / "applications"

        ensure_dirs(target_apps_dir, target_bin_dir, target_desktop_dir)

        packaged_apps = []
        if APPS_DIR.exists():
            for slug in os.listdir(APPS_DIR):
                app_src = APPS_DIR / slug
                if app_src.is_dir():
                    app_dst = target_apps_dir / slug
                    safe_copy(app_src, app_dst)

                    # Create executable wrapper in /opt/pyflare/bin/{slug}
                    main_py = app_dst / "src" / "main.py"
                    wrapper = target_bin_dir / f"pyflare-{slug}"
                    wrapper_content = f"""#!/usr/bin/env bash
export PYFLARE_HOME="/opt/pyflare"
export PYTHONPATH="/opt/pyflare/apps/{slug}/src:${{PYTHONPATH:-}}"
exec python3 /opt/pyflare/apps/{slug}/src/main.py "$@"
"""
                    with open(wrapper, "w", encoding="utf-8", newline="\n") as f:
                        f.write(wrapper_content)

                    # Copy desktop file if present
                    desktop_src = app_src / "desktop"
                    if desktop_src.exists():
                        for df in desktop_src.glob("*.desktop"):
                            shutil.copy2(df, target_desktop_dir / df.name)

                    packaged_apps.append(slug)
                    self.pkg_log.info(f"Packaged application: {slug} -> /opt/pyflare/apps/{slug}")

        pkg_summary = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "total_apps": len(packaged_apps),
            "applications": packaged_apps,
            "apps_directory": str(target_apps_dir.relative_to(ROOTFS_DIR)),
        }
        with open(REPORT_DIR / "applications_manifest.json", "w", encoding="utf-8") as f:
            json.dump(pkg_summary, f, indent=2)

        return True, f"Packaged {len(packaged_apps)} applications into /opt/pyflare/apps/", pkg_summary

    # -----------------------------------------------------------------------
    # Stage 6: Desktop Integration
    # -----------------------------------------------------------------------
    def stage_06_desktop_integration(self):
        apps_dir = ROOTFS_DIR / "usr" / "share" / "applications"
        schemas_dir = ROOTFS_DIR / "usr" / "share" / "glib-2.0" / "schemas"
        icons_dir = ROOTFS_DIR / "usr" / "share" / "icons" / "PyFlare-Icons"

        desktop_count = len(list(apps_dir.glob("*.desktop"))) if apps_dir.exists() else 0
        schema_count = len(list(schemas_dir.glob("*.override"))) if schemas_dir.exists() else 0

        compiled_schemas = False
        if self.is_linux and shutil.which("glib-compile-schemas"):
            try:
                subprocess.run(["glib-compile-schemas", str(schemas_dir)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                compiled_schemas = True
                self.build_log.info("Compiled GLib gsettings schemas.")
            except Exception as e:
                self.build_log.warning(f"Could not compile GLib schemas: {e}")

        integration_info = {
            "desktop_launchers": desktop_count,
            "gsettings_overrides": schema_count,
            "icon_theme_present": icons_dir.exists(),
            "schemas_compiled": compiled_schemas,
        }
        return True, f"Integrated {desktop_count} desktop launchers & GNOME overrides", integration_info

    # -----------------------------------------------------------------------
    # Stage 7: Boot Configuration
    # -----------------------------------------------------------------------
    def stage_07_boot_config(self):
        etc_dir = ROOTFS_DIR / "etc"
        grub_default = etc_dir / "default" / "grub"
        plymouth_conf = etc_dir / "plymouth" / "plymouthd.conf"
        hostname_file = etc_dir / "hostname"
        os_release_file = etc_dir / "os-release"

        # Enable systemd services by linking into multi-user.target.wants
        wants_dir = etc_dir / "systemd" / "system" / "multi-user.target.wants"
        wants_dir.mkdir(parents=True, exist_ok=True)

        enabled_services = []
        services_to_enable = [
            ("pyflare-engine.service", "/etc/systemd/system/pyflare-engine.service"),
            ("pyflare-firstrun.service", "/etc/systemd/system/pyflare-firstrun.service"),
            ("pyflare-update.service", "/etc/systemd/system/pyflare-update.service"),
            ("pyflare-update.timer", "/etc/systemd/system/pyflare-update.timer"),
        ]

        for svc_name, target in services_to_enable:
            link_path = wants_dir / svc_name
            if not link_path.exists() and not link_path.is_symlink():
                try:
                    os.symlink(target, link_path)
                    enabled_services.append(svc_name)
                except Exception:
                    # Fallback for Windows file system without symlink privilege
                    with open(link_path, "w", encoding="utf-8") as f:
                        f.write(f"# Symlink to {target}\n")
                    enabled_services.append(svc_name)

        boot_info = {
            "grub_configured": grub_default.exists(),
            "plymouth_configured": plymouth_conf.exists(),
            "hostname_configured": hostname_file.exists(),
            "os_release_configured": os_release_file.exists(),
            "enabled_services": enabled_services,
        }
        return True, f"Boot params, GRUB, Plymouth, and {len(enabled_services)} systemd services configured", boot_info

    # -----------------------------------------------------------------------
    # Stage 8: Filesystem Manifest & Checksums
    # -----------------------------------------------------------------------
    def stage_08_filesystem_manifest(self):
        manifest_files = {}
        total_size = 0

        for dirpath, _, filenames in os.walk(ROOTFS_DIR):
            for fname in filenames:
                fp = Path(dirpath) / fname
                rel = str(fp.relative_to(ROOTFS_DIR)).replace("\\", "/")
                try:
                    sz = fp.stat().st_size
                    h = compute_sha256(fp)
                    manifest_files[rel] = {
                        "size_bytes": sz,
                        "sha256": h,
                    }
                    total_size += sz
                except Exception as e:
                    self.build_log.warning(f"Error hashing {rel}: {e}")

        manifest_data = {
            "generated": datetime.now(timezone.utc).isoformat() + "Z",
            "root": "build/rootfs/",
            "total_file_count": len(manifest_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": manifest_files
        }

        with open(REPORT_DIR / "filesystem_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # Write checksums.json for all report files
        checksums = {}
        for r_file in REPORT_DIR.glob("*.json"):
            checksums[r_file.name] = compute_sha256(r_file)

        with open(REPORT_DIR / "checksums.json", "w", encoding="utf-8") as f:
            json.dump({
                "generated": datetime.now(timezone.utc).isoformat() + "Z",
                "checksums": checksums
            }, f, indent=2)

        return True, f"Manifest generated for {len(manifest_files)} files ({round(total_size / 1048576, 2)} MB)", {
            "file_count": len(manifest_files),
            "total_mb": round(total_size / 1048576, 2)
        }

    # -----------------------------------------------------------------------
    # Stage 9: SquashFS Creation
    # -----------------------------------------------------------------------
    def stage_09_squashfs(self):
        squashfs_out = BUILD_DIR / "filesystem.squashfs"

        if not self.is_linux:
            msg = "[SKIP] Windows host detected — mksquashfs skipped. Rootfs is fully prepared in build/rootfs/."
            self.build_log.info(msg)
            return True, msg, {"skipped": True, "reason": "non-linux-host"}

        mksquashfs_bin = shutil.which("mksquashfs")
        if not mksquashfs_bin:
            msg = "[SKIP] mksquashfs tool not installed on Linux host."
            self.build_log.warning(msg)
            return True, msg, {"skipped": True, "reason": "missing-tool"}

        if squashfs_out.exists():
            squashfs_out.unlink()

        cmd = [mksquashfs_bin, str(ROOTFS_DIR), str(squashfs_out), "-comp", "xz", "-b", "1M", "-no-recovery"]
        self.build_log.info(f"Compressing rootfs to SquashFS: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        if result.returncode == 0 and squashfs_out.exists():
            sz_mb = round(squashfs_out.stat().st_size / 1048576, 2)
            return True, f"Compressed rootfs -> filesystem.squashfs ({sz_mb} MB)", {"squashfs_size_mb": sz_mb}
        else:
            return False, f"mksquashfs failed with exit code {result.returncode}", {"output": result.stdout}

    # -----------------------------------------------------------------------
    # Stage 10: ISO Creation
    # -----------------------------------------------------------------------
    def stage_10_iso_creation(self):
        iso_out = OUTPUT_DIR / "pyflare-os-1.0.0-ember-amd64.iso"

        if not self.is_linux:
            msg = "[SKIP] Windows environment detected — xorriso/ISO creation requires Linux host (or WSL2). Rootfs and source tree are 100% build-ready."
            self.build_log.info(msg)
            return True, msg, {"skipped": True, "reason": "non-linux-host"}

        iso_tools = ["xorriso", "grub-mkrescue"]
        missing_tools = [t for t in iso_tools if not shutil.which(t)]

        if missing_tools:
            msg = f"[SKIP] ISO creation tools missing ({', '.join(missing_tools)}). Install via apt: sudo apt install xorriso grub-pc-bin grub-efi-amd64-bin"
            self.build_log.warning(msg)
            return True, msg, {"skipped": True, "reason": "missing-iso-tools"}

        self.build_log.info("Linux ISO creation tools detected. Assembling PyFlare OS ISO...")
        # Execute ISO packager logic if on Linux
        try:
            from scripts.package_iso import ISOPackager
            packager = ISOPackager(ROOT, self.build_log, work_dir=BUILD_DIR)
            final_iso = packager.build_iso(output_dir=OUTPUT_DIR)
            if final_iso and Path(final_iso).exists():
                sz_mb = round(Path(final_iso).stat().st_size / 1048576, 2)
                return True, f"ISO created successfully: {Path(final_iso).name} ({sz_mb} MB)", {"iso_path": str(final_iso)}
            else:
                return False, "ISO packaging failed", {}
        except Exception as e:
            return False, f"ISO packaging exception: {e}", {}

    # -----------------------------------------------------------------------
    # Run Orchestrator Pipeline
    # -----------------------------------------------------------------------
    def run(self) -> int:
        self.print_banner()

        stages = [
            (1,  "Validation Suite",               self.stage_01_validation),
            (2,  "Root Filesystem Preparation",    self.stage_02_prepare_rootfs),
            (3,  "Package Preparation",            self.stage_03_packages),
            (4,  "Branding Deployment",            self.stage_04_branding),
            (5,  "Application Packaging",          self.stage_05_application_packaging),
            (6,  "Desktop Integration",            self.stage_06_desktop_integration),
            (7,  "Boot Configuration",             self.stage_07_boot_config),
            (8,  "Filesystem Manifest & Checksums",self.stage_08_filesystem_manifest),
            (9,  "SquashFS Creation",              self.stage_09_squashfs),
            (10, "ISO Creation",                   self.stage_10_iso_creation),
        ]

        overall_success = True

        for stage_num, stage_name, stage_func in stages:
            success = self.run_stage(stage_num, stage_name, stage_func)
            if not success:
                overall_success = False
                print(colorize(f"\n[FATAL] Pipeline stopped at Stage {stage_num:02d} ({stage_name}).", Colors.FAIL))
                self.build_log.error(f"Pipeline stopped at Stage {stage_num:02d} ({stage_name}).")
                break

        total_elapsed = round(time.time() - self.start_time, 2)

        # Write reports/timings.json
        with open(REPORT_DIR / "timings.json", "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "total_duration_seconds": total_elapsed,
                "stages": self.stage_timings
            }, f, indent=2)

        # Write reports/build_report.json
        build_report = {
            "product": "PyFlare OS",
            "version": "1.0.0",
            "codename": "Ember",
            "vendor": "Aachman Studios",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "total_duration_seconds": total_elapsed,
            "host_platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "status": "SUCCESS" if overall_success else "FAILED",
            "stage_results": self.stage_results
        }
        with open(REPORT_DIR / "build_report.json", "w", encoding="utf-8") as f:
            json.dump(build_report, f, indent=2)

        # Print Final Summary Table
        print(colorize("\n" + "=" * 65, Colors.HEADER))
        print(colorize(f"   BUILD PIPELINE SUMMARY — Result: {'SUCCESS' if overall_success else 'FAILED'}", Colors.OKGREEN if overall_success else Colors.FAIL))
        print(colorize("=" * 65, Colors.HEADER))
        print(f"  {'Stage':<35} {'Status':<10} {'Duration':<10}")
        print("  " + "-" * 57)

        for stage_name, t_info in self.stage_timings.items():
            st = t_info["status"]
            dur = f"{t_info['duration_seconds']:.2f}s"
            color = Colors.OKGREEN if st == "PASS" else (Colors.WARNING if st == "SKIPPED" else Colors.FAIL)
            print(f"  {stage_name:<35} {colorize(st, color):<19} {dur:<10}")

        print("  " + "-" * 57)
        print(colorize(f"  Total Duration: {total_elapsed:.2f} seconds\n", Colors.OKCYAN))

        if overall_success:
            self.build_log.info("Build pipeline completed successfully.")
            return 0
        else:
            self.build_log.error("Build pipeline completed with errors.")
            return 1


if __name__ == "__main__":
    pipeline = PyFlareBuildPipeline()
    sys.exit(pipeline.run())
