#!/usr/bin/env python3
"""
PyFlare OS — Fast ISO Remaster & GDM3 / Boot Repair
---------------------------------------------------
Solves the "stuck on ubuntu screen" bug:
1. Fixes broken /etc/systemd/system/display-manager.service symlink (was pointing to non-existent lightdm).
2. Enables gdm3 as the active display manager.
3. Sets WaylandEnable=false in /etc/gdm3/custom.conf (prevents VirtualBox VBoxSVGA Wayland freeze).
4. Enables AutomaticLogin for 'pyflare' user.
5. Masks blocking cloud-init and systemd-networkd-wait-online services.
6. Layers all PyFlare branding and applications on top of the 2.85 GB base Ubuntu OS via Casper OverlayFS.
7. Assembles hybrid bootable ISO using xorriso.
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    t0 = time.time()
    print("=== PyFlare OS Fast Remaster & Boot Repair ===")

    pyflare_root = Path(__file__).resolve().parent.parent
    output_dir = pyflare_root / "output"
    output_dir.mkdir(exist_ok=True)
    target_iso = output_dir / "pyflare-os-1.0.0-ember-amd64.iso"

    # Base source ISO with the full 2.85 GB Ubuntu rootfs
    source_iso = Path("/mnt/c/Users/Aachman_the_great/.gemini/antigravity/scratch/Appsuite/PyFlare/output/pyflare-os-1.0.0-ember-amd64.iso")
    if not source_iso.exists():
        # Fallback path if accessed differently
        alt_source = pyflare_root.parent / "Pyflare" / "Appsuite" / "PyFlare" / "Isos" / "ubuntu-24.04.4-live-server-amd64.iso"
        if alt_source.exists():
            source_iso = alt_source
        else:
            print(f"ERROR: Source ISO not found at {source_iso}")
            sys.exit(1)

    print(f"Using base source ISO: {source_iso} ({source_iso.stat().st_size // (1024*1024)} MB)")

    # Working staging directories in fast local /var/tmp (avoids 9p shared folder overhead)
    stage_root = Path("/var/tmp/pyflare_iso_rebuild")
    stage_root.mkdir(parents=True, exist_ok=True)

    iso_extract = stage_root / "iso_content"
    iso_extract.mkdir(parents=True, exist_ok=True)
    casper_dir = iso_extract / "casper"
    casper_dir.mkdir(parents=True, exist_ok=True)
    boot_grub_dir = iso_extract / "boot" / "grub"
    boot_grub_dir.mkdir(parents=True, exist_ok=True)
    disk_dir = iso_extract / ".disk"
    disk_dir.mkdir(parents=True, exist_ok=True)
    (disk_dir / "info").write_text("PyFlare OS 1.0.0 Ember - Game Dev Edition")

    dst_base_sq = casper_dir / "ubuntu-server-minimal.squashfs"
    pristine_initrd = stage_root / "initrd.pristine"
    if not (dst_base_sq.exists() and (casper_dir / "vmlinuz").exists() and pristine_initrd.exists()):
        mnt_dir = stage_root / "mnt_source"
        mnt_dir.mkdir(parents=True, exist_ok=True)
        print("Mounting base ISO to extract rootfs and pristine boot assets...")
        subprocess.run(["mount", "-o", "loop,ro", str(source_iso), str(mnt_dir)], check=True)
        try:
            print("Extracting kernel and pristine initrd...")
            shutil.copy2(mnt_dir / "casper" / "vmlinuz", casper_dir / "vmlinuz")
            shutil.copy2(mnt_dir / "casper" / "initrd", pristine_initrd)
            shutil.copy2(pristine_initrd, casper_dir / "initrd")

            src_base_sq = mnt_dir / "casper" / "ubuntu-server-minimal.squashfs"
            print(f"Staging base Ubuntu rootfs ({src_base_sq.stat().st_size // (1024*1024)} MB)...")
            subprocess.run(["cp", str(src_base_sq), str(dst_base_sq)], check=True)

            if (mnt_dir / "casper" / "filesystem.size").exists():
                shutil.copy2(mnt_dir / "casper" / "filesystem.size", casper_dir / "filesystem.size")
            else:
                (casper_dir / "filesystem.size").write_text(str(src_base_sq.stat().st_size) + "\n")
        finally:
            subprocess.run(["umount", str(mnt_dir)], check=False)
    else:
        print(f"Base Ubuntu rootfs already cached at {dst_base_sq} ({dst_base_sq.stat().st_size // (1024*1024)} MB). Fast rebuild enabled!")
        shutil.copy2(pristine_initrd, casper_dir / "initrd")

    # Patch initrd Casper debconf FIFO non-blocking fix
    print("Applying Casper initrd non-blocking FIFO patch...")
    from patch_initrd import patch_initrd_file
    patched_initrd = patch_initrd_file(casper_dir / "initrd")
    (casper_dir / "initrd").write_bytes(patched_initrd)
    print(f"Patched initrd written ({len(patched_initrd)} bytes).")

    # 3. Build the PyFlare Overlay layer
    print("Constructing PyFlare Desktop & Boot Configuration Overlay...")
    overlay_dir = stage_root / "overlay"
    if overlay_dir.exists():
        subprocess.run(["rm", "-rf", str(overlay_dir)], check=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    # Copy files from repository filesystem/ overlay
    repo_fs = pyflare_root / "filesystem"
    if repo_fs.exists():
        print(f"Merging repo filesystem overlay from {repo_fs}...")
        subprocess.run(["cp", "-a", f"{repo_fs}/.", str(overlay_dir)], check=True)

    # Copy applications and wrappers
    apps_target = overlay_dir / "opt" / "pyflare" / "apps"
    bin_target = overlay_dir / "opt" / "pyflare" / "bin"
    desktop_target = overlay_dir / "usr" / "share" / "applications"
    apps_target.mkdir(parents=True, exist_ok=True)
    bin_target.mkdir(parents=True, exist_ok=True)
    desktop_target.mkdir(parents=True, exist_ok=True)

    repo_apps = pyflare_root / "applications"
    if repo_apps.exists():
        for app_dir in repo_apps.iterdir():
            if app_dir.is_dir():
                slug = app_dir.name
                subprocess.run(["cp", "-a", str(app_dir), str(apps_target / slug)], check=True)
                wrapper = bin_target / f"pyflare-{slug}"
                wrapper.write_text(f"""#!/usr/bin/env bash
export PYFLARE_HOME="/opt/pyflare"
export PYTHONPATH="/opt/pyflare/apps/{slug}/src:${{PYTHONPATH:-}}"
exec python3 /opt/pyflare/apps/{slug}/src/main.py "$@"
""")
                wrapper.chmod(0o755)
                # Copy desktop entry if present
                for df in (app_dir / "desktop").glob("*.desktop"):
                    shutil.copy2(df, desktop_target / df.name)

    # Copy control plane
    repo_cp = pyflare_root / "control_plane"
    if repo_cp.exists():
        cp_dst = overlay_dir / "opt" / "pyflare" / "control_plane"
        subprocess.run(["cp", "-a", str(repo_cp), str(cp_dst)], check=True)
        cp_wrapper = bin_target / "pyflare-control"
        cp_wrapper.write_text("""#!/usr/bin/env bash
export PYFLARE_HOME="/opt/pyflare"
export PYTHONPATH="/opt/pyflare/control_plane/src:${PYTHONPATH:-}"
exec python3 -m pyflare_control.cli "$@"
""")
        cp_wrapper.chmod(0o755)

    # FIX 1: Display Manager & Systemd services
    print("Applying GDM3 display manager and boot fixes...")
    sysd_dir = overlay_dir / "etc" / "systemd" / "system"
    sysd_dir.mkdir(parents=True, exist_ok=True)
    graphical_wants = sysd_dir / "graphical.target.wants"
    graphical_wants.mkdir(parents=True, exist_ok=True)

    # Set default target to graphical
    default_target = sysd_dir / "default.target"
    if default_target.exists() or default_target.is_symlink():
        default_target.unlink()
    os.symlink("/usr/lib/systemd/system/graphical.target", str(default_target))

    # Point display-manager.service to gdm3.service
    dm_service = sysd_dir / "display-manager.service"
    if dm_service.exists() or dm_service.is_symlink():
        dm_service.unlink()
    os.symlink("/usr/lib/systemd/system/gdm3.service", str(dm_service))

    dm_wants = graphical_wants / "display-manager.service"
    if dm_wants.exists() or dm_wants.is_symlink():
        dm_wants.unlink()
    os.symlink("/usr/lib/systemd/system/gdm3.service", str(dm_wants))

    # Mask broken lightdm so it cannot fail graphical.target
    for lm in [sysd_dir / "lightdm.service", graphical_wants / "lightdm.service"]:
        if lm.exists() or lm.is_symlink():
            lm.unlink()
        os.symlink("/dev/null", str(lm))

    # Mask slow cloud-init, wait-online, and unnecessary background services that cause boot freezes
    for block_unit in [
        "cloud-init.service",
        "cloud-init-local.service",
        "cloud-config.service",
        "cloud-final.service",
        "systemd-networkd-wait-online.service",
        "NetworkManager-wait-online.service",
        "multipathd.service",
        "multipathd.socket",
        "ModemManager.service",
        "apt-daily.service",
        "apt-daily-upgrade.service"
    ]:
        unit_path = sysd_dir / block_unit
        if unit_path.exists() or unit_path.is_symlink():
            unit_path.unlink()
        os.symlink("/dev/null", str(unit_path))

    # Neutralize VM-incompatible Settings Daemons so GNOME session initialization never blocks
    user_sysd = overlay_dir / "etc" / "systemd" / "user"
    user_sysd.mkdir(parents=True, exist_ok=True)
    dummy_units = [
        "org.gnome.SettingsDaemon.UsbProtection.service",
        "org.gnome.SettingsDaemon.Smartcard.service",
        "org.gnome.SettingsDaemon.Wacom.service",
        "org.gnome.SettingsDaemon.PrintNotifications.service",
        "org.gnome.SettingsDaemon.Rfkill.service",
        "org.gnome.SettingsDaemon.Sharing.service",
        "org.gnome.SettingsDaemon.Wwan.service",
    ]
    for unit_name in dummy_units:
        u_path = user_sysd / unit_name
        u_path.write_text("""[Unit]
Description=GNOME VM Dummy Service
PartOf=gnome-session-initialized.target

[Service]
Type=oneshot
ExecStart=/bin/true
RemainAfterExit=yes

[Install]
WantedBy=gnome-session-initialized.target
""")

    # Mask gnome-session-failed screen in user systemd so minor issues can NEVER block desktop
    for gsf in [
        "gnome-session-failed.service",
        "gnome-session-failed.target"
    ]:
        for prefix in [overlay_dir / "etc" / "systemd" / "user", overlay_dir / "usr" / "lib" / "systemd" / "user"]:
            prefix.mkdir(parents=True, exist_ok=True)
            gsf_path = prefix / gsf
            if gsf_path.exists() or gsf_path.is_symlink():
                gsf_path.unlink()
            os.symlink("/dev/null", str(gsf_path))

    # Physically replace gnome-session-failed binary with exit 0 dummy
    for bin_dir in [overlay_dir / "usr" / "libexec", overlay_dir / "usr" / "lib" / "gnome-session"]:
        bin_dir.mkdir(parents=True, exist_ok=True)
        gsf_bin = bin_dir / "gnome-session-failed"
        gsf_bin.write_text("#!/bin/sh\nexit 0\n")
        gsf_bin.chmod(0o755)

    # System-wide and session-wide environment overrides
    env_d = overlay_dir / "etc" / "environment.d"
    env_d.mkdir(parents=True, exist_ok=True)
    (env_d / "60-virtualbox.conf").write_text("""LIBGL_ALWAYS_SOFTWARE=1
GALLIUM_DRIVER=llvmpipe
MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
MUTTER_DEBUG_FORCE_EGL_STREAM=0
CLUTTER_ENABLE_DIAGNOSTIC=0
""")

    # Blacklist efi_pstore to prevent BIOS VM boot pause
    modprobe_d = overlay_dir / "etc" / "modprobe.d"
    modprobe_d.mkdir(parents=True, exist_ok=True)
    (modprobe_d / "blacklist-vbox.conf").write_text("blacklist efi_pstore\n")


    # Enable PyFlare systemd units
    multi_user_wants = sysd_dir / "multi-user.target.wants"
    multi_user_wants.mkdir(parents=True, exist_ok=True)
    swap_wants = sysd_dir / "swap.target.wants"
    swap_wants.mkdir(parents=True, exist_ok=True)

    for unit_name, target_dir in [
        ("pyflare-zram.service", swap_wants),
        ("pyflare-firstrun.service", multi_user_wants),
        ("pyflare-engine.service", multi_user_wants),
    ]:
        wants_link = target_dir / unit_name
        if wants_link.exists() or wants_link.is_symlink():
            wants_link.unlink()
        os.symlink(f"/etc/systemd/system/{unit_name}", str(wants_link))

    zram_bin = overlay_dir / "opt" / "pyflare" / "bin" / "pyflare-zram-setup"
    if zram_bin.exists():
        zram_bin.chmod(0o755)
    engine_bin = overlay_dir / "opt" / "pyflare" / "engine" / "pyflare-engine"
    if engine_bin.exists():
        engine_bin.chmod(0o755)

    # FIX 2: GDM3 configuration (Disable Wayland for VirtualBox, Enable AutoLogin)
    gdm_dir = overlay_dir / "etc" / "gdm3"
    gdm_dir.mkdir(parents=True, exist_ok=True)
    gdm_conf = gdm_dir / "custom.conf"
    gdm_conf.write_text("""# PyFlare GDM3 Configuration
[daemon]
WaylandEnable=false
AutomaticLoginEnable=true
AutomaticLogin=pyflare
TimedLoginEnable=false
DefaultSession=gnome-xorg

[security]
AllowRoot=false

[xdmcp]
Enable=false

[chooser]
Multicast=false

[debug]
Enable=false
""")

    # FIX 3: Casper Live User Configuration
    casper_conf = overlay_dir / "etc" / "casper.conf"
    casper_conf.write_text("""export USERNAME=pyflare
export USERFULLNAME="PyFlare Developer"
export HOST=pyflare
export BUILD_SYSTEM=Ubuntu
""")

    # FIX 4: Sudoers passwordless configuration for pyflare
    sudoers_dir = overlay_dir / "etc" / "sudoers.d"
    sudoers_dir.mkdir(parents=True, exist_ok=True)
    sudoers_dir.chmod(0o750)
    sudo_file = sudoers_dir / "99-pyflare-nopasswd"
    sudo_file.write_text("pyflare ALL=(ALL) NOPASSWD:ALL\n")
    sudo_file.chmod(0o440)

    # FIX 5: Ensure 'gdm' system user, group, PAM configs, and Xsession are fully configured
    print("Extracting base user database and PAM configs to apply GDM fixes...")
    subprocess.run([
        "unsquashfs", "-f", "-d", str(overlay_dir), str(dst_base_sq),
        "etc/passwd", "etc/group", "etc/shadow", "etc/pam.d", "etc/gdm3", "etc/xdg/autostart"
    ], check=True, stdout=subprocess.DEVNULL)

    # Ensure system users needed by GNOME, GDM, colord, and D-Bus services exist
    sys_users = [
        ("gdm", 120, 125, "Gnome Display Manager", "/var/lib/gdm3", "/bin/false"),
        ("colord", 121, 126, "colord colour management daemon", "/var/lib/colord", "/usr/sbin/nologin"),
        ("geoclue", 122, 127, "Geoinformation service", "/var/lib/geoclue", "/usr/sbin/nologin"),
        ("avahi", 123, 128, "Avahi mDNS daemon", "/run/avahi-daemon", "/usr/sbin/nologin"),
        ("rtkit", 124, 129, "RealtimeKit", "/proc", "/usr/sbin/nologin"),
    ]
    pw_file = overlay_dir / "etc" / "passwd"
    pw_content = pw_file.read_text()
    for u_name, u_uid, u_gid, u_gecos, u_home, u_shell in sys_users:
        if f"{u_name}:" not in pw_content:
            pw_content += f"{u_name}:x:{u_uid}:{u_gid}:{u_gecos}:{u_home}:{u_shell}\n"
    pw_file.write_text(pw_content)

    gr_file = overlay_dir / "etc" / "group"
    gr_content = gr_file.read_text()
    for u_name, _, u_gid, _, _, _ in sys_users:
        if f"{u_name}:" not in gr_content:
            gr_content += f"{u_name}:x:{u_gid}:\n"
    
    # Ensure pyflare is in necessary interactive & hardware groups
    gr_lines = []
    for line in gr_content.splitlines():
        parts = line.split(":")
        if len(parts) >= 4 and parts[0] in ("video", "render", "audio", "input", "adm", "sudo", "dip", "plugdev"):
            members = [m for m in parts[3].split(",") if m]
            if "pyflare" not in members:
                members.append("pyflare")
            parts[3] = ",".join(members)
            gr_lines.append(":".join(parts))
        else:
            gr_lines.append(line)
    gr_file.write_text("\n".join(gr_lines) + "\n")

    sh_file = overlay_dir / "etc" / "shadow"
    sh_content = sh_file.read_text()
    for u_name, _, _, _, _, _ in sys_users:
        if f"{u_name}:" not in sh_content:
            sh_content += f"{u_name}:*:20000:0:99999:7:::\n"
    
    # Set verified SHA-512 crypt password 'appsuite' for pyflare and root
    appsuite_hash = "$6$pyflareos$mGFxw8mj4h5FI8JQt5gW9PkbvdCoq.br97hcR4.5Ru1nkMuMdTD9N1/iMccBtRfdzh8LLSFwgg.MtNHkFlNZ51"
    new_sh_lines = []
    for line in sh_content.splitlines():
        if line.startswith("pyflare:"):
            parts = line.split(":")
            parts[1] = appsuite_hash
            new_sh_lines.append(":".join(parts))
        elif line.startswith("root:"):
            parts = line.split(":")
            parts[1] = appsuite_hash
            new_sh_lines.append(":".join(parts))
        else:
            new_sh_lines.append(line)
    if not any(l.startswith("pyflare:") for l in new_sh_lines):
        new_sh_lines.append(f"pyflare:{appsuite_hash}:20000:0:99999:7:::")
    sh_file.write_text("\n".join(new_sh_lines) + "\n")

    # Rename all .dpkg-new files in /etc/pam.d and /etc/gdm3 so PAM and GDM can find them
    for dpkg_f in overlay_dir.glob("etc/**/*.dpkg-new"):
        target_clean = dpkg_f.parent / dpkg_f.name[:-9]
        if target_clean.exists():
            target_clean.unlink()
        dpkg_f.rename(target_clean)

    # Ensure /etc/gdm3/Xsession is executable
    xsession = overlay_dir / "etc" / "gdm3" / "Xsession"
    if xsession.exists():
        xsession.chmod(0o755)

    # Ensure PyFlare cursor theme symlink points to Adwaita
    icons_dir = overlay_dir / "usr" / "share" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    pyflare_cursor = icons_dir / "PyFlare"
    if pyflare_cursor.exists() or pyflare_cursor.is_symlink():
        pyflare_cursor.unlink()
    pyflare_cursor.symlink_to("Adwaita")

    # Re-apply custom.conf and casper.conf over extracted ones
    gdm_conf.write_text("""# PyFlare GDM3 Configuration
[daemon]
WaylandEnable=false
AutomaticLoginEnable=true
AutomaticLogin=pyflare
TimedLoginEnable=false
DefaultSession=gnome-xorg

[security]
AllowRoot=false

[xdmcp]
Enable=false

[chooser]
Multicast=false

[debug]
Enable=false
""")
    casper_conf.write_text("""export USERNAME=pyflare
export USERFULLNAME="PyFlare Developer"
export HOST=pyflare
export BUILD_SYSTEM=Ubuntu
""")

    # Compile GLib schemas
    schemas_dir = overlay_dir / "usr" / "share" / "glib-2.0" / "schemas"
    if schemas_dir.exists() and shutil.which("glib-compile-schemas"):
        try:
            subprocess.run(["unsquashfs", "-f", "-d", str(overlay_dir), str(dst_base_sq), "usr/share/glib-2.0/schemas"], check=False, stdout=subprocess.DEVNULL)
            subprocess.run(["glib-compile-schemas", str(schemas_dir)], check=False, stdout=subprocess.DEVNULL)
            print("GLib schemas compiled successfully.")
        except Exception as e:
            print(f"Warning compiling schemas: {e}")

    # Ensure strict permissions on sudoers.d before squashfs compression
    sd = overlay_dir / "etc" / "sudoers.d"
    if sd.exists():
        os.chmod(str(sd), 0o750)
        for sf in sd.iterdir():
            os.chmod(str(sf), 0o440)

    # Plymouth quit safety service to prevent splash hang
    pq_service = sysd_dir / "plymouth-quit-pyflare.service"
    pq_service.write_text("""[Unit]
Description=PyFlare Plymouth Quit Safety
After=gdm3.service
Wants=gdm3.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c "/usr/bin/plymouth quit || true"
RemainAfterExit=yes

[Install]
WantedBy=graphical.target
""")
    pq_wants = graphical_wants / "plymouth-quit-pyflare.service"
    if pq_wants.exists() or pq_wants.is_symlink():
        pq_wants.unlink()
    os.symlink("/etc/systemd/system/plymouth-quit-pyflare.service", str(pq_wants))

    # AccountsService configuration for user pyflare (forces gnome-xorg session)
    acc_dir = overlay_dir / "var" / "lib" / "AccountsService" / "users"
    acc_dir.mkdir(parents=True, exist_ok=True)
    (acc_dir / "pyflare").write_text("""[User]
Session=gnome-xorg
XSession=gnome-xorg
SystemAccount=false
""")

    # Set proper ownership: system files owned by root, /home/pyflare owned by 1000:1000
    subprocess.run(["chown", "-R", "0:0", str(overlay_dir)], check=True)
    # Fix systemd unit permissions so systemd doesn't warn about executable/world-writable units
    subprocess.run(["find", str(overlay_dir / "etc" / "systemd"), "-type", "f", "-name", "*.service", "-exec", "chmod", "644", "{}", "+"], check=False)
    subprocess.run(["find", str(overlay_dir / "etc" / "systemd"), "-type", "f", "-name", "*.timer", "-exec", "chmod", "644", "{}", "+"], check=False)
    # Ensure all scripts in /opt/pyflare/bin are 755
    if (overlay_dir / "opt" / "pyflare" / "bin").exists():
        subprocess.run(["chmod", "-R", "755", str(overlay_dir / "opt" / "pyflare" / "bin")], check=False)
    home_pyflare = overlay_dir / "home" / "pyflare"
    if home_pyflare.exists():
        subprocess.run(["chown", "-R", "1000:1000", str(home_pyflare)], check=True)
        subprocess.run(["chmod", "750", str(home_pyflare)], check=True)


    # 4. Compress overlay into SquashFS
    print("Compressing overlay SquashFS layer...")
    overlay_sq = stage_root / "overlay.squashfs"
    if overlay_sq.exists():
        overlay_sq.unlink()
    subprocess.run([
        "mksquashfs", str(overlay_dir), str(overlay_sq),
        "-noappend", "-comp", "xz", "-b", "512K", "-no-recovery"
    ], check=True, stdout=subprocess.DEVNULL)
    print(f"Overlay layer compressed: {overlay_sq.stat().st_size // 1024} KB")

    # In Casper OverlayFS stack, populate upper layers so our fixes override bottom rootfs
    upper_layers = [
        "ubuntu-server-minimal.ubuntu-server.squashfs",
        "ubuntu-server-minimal.ubuntu-server.installer.squashfs",
        "ubuntu-server-minimal.ubuntu-server.installer.generic.squashfs"
    ]
    for layer_name in upper_layers:
        shutil.copy2(overlay_sq, casper_dir / layer_name)
    print(f"Populated {len(upper_layers)} Casper overlay layers with boot & GDM3 fixes.")

    # 5. Create GRUB boot configuration
    grub_cfg = boot_grub_dir / "grub.cfg"
    grub_cfg.write_text("""set timeout=2
set default=0

menuentry "Start PyFlare OS Desktop (GNOME Auto-Login)" {
    set gfxpayload=keep
    linux /casper/vmlinuz boot=casper ignore_uuid live-media-path=/casper systemd.unit=graphical.target fsck.mode=skip mitigations=off noprompt noeject ---
    initrd /casper/initrd
}

menuentry "Start PyFlare OS Desktop (Safe Graphics - Xorg)" {
    set gfxpayload=keep
    linux /casper/vmlinuz boot=casper ignore_uuid live-media-path=/casper systemd.unit=graphical.target nomodeset mitigations=off noprompt noeject quiet splash ---
    initrd /casper/initrd
}

menuentry "Start PyFlare OS (Debug Console - Verbose Boot)" {
    linux /casper/vmlinuz boot=casper ignore_uuid live-media-path=/casper systemd.unit=graphical.target systemd.log_level=debug noprompt noeject console=tty1 ---
    initrd /casper/initrd
}
""")

    # 6. Generate Hybrid Bootable ISO with grub-mkrescue
    print("Generating final hybrid bootable ISO with grub-mkrescue...")
    temp_iso = stage_root / "pyflare-os-1.0.0-ember-amd64.iso"
    if temp_iso.exists():
        temp_iso.unlink()

    cmd = [
        "grub-mkrescue",
        "-o", str(temp_iso),
        str(iso_extract),
        "--volid", "PYFLARE_OS",
        "--appid", "PyFlare OS 1.0.0 Ember",
        "--publisher", "Aachman Studios"
    ]
    subprocess.run(cmd, check=True)

    if target_iso.exists():
        try:
            target_iso.unlink()
        except Exception as e:
            print(f"Warning unlinking existing target ISO: {e}")

    shutil.copy2(temp_iso, target_iso)
    elapsed = time.time() - t0
    iso_size_mb = target_iso.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: ISO generated at {target_iso} ({iso_size_mb:.2f} MB) in {elapsed:.2f}s!")

if __name__ == "__main__":
    main()
