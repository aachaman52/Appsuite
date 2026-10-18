import subprocess
import tempfile
from pathlib import Path

base_sq = Path("/var/tmp/pyflare_iso_rebuild/iso_content/casper/ubuntu-server-minimal.squashfs")
overlay_sq = Path("/var/tmp/pyflare_iso_rebuild/overlay.squashfs")

stage = Path("/tmp/test_casper_root")
stage.mkdir(parents=True, exist_ok=True)
mnt_base = stage / "base"
mnt_base.mkdir(parents=True, exist_ok=True)
mnt_overlay = stage / "overlay"
mnt_overlay.mkdir(parents=True, exist_ok=True)
work = stage / "work"
work.mkdir(parents=True, exist_ok=True)
upper = stage / "upper"
upper.mkdir(parents=True, exist_ok=True)
merged = stage / "merged"
merged.mkdir(parents=True, exist_ok=True)

subprocess.run(["mount", "-o", "loop,ro", str(base_sq), str(mnt_base)], check=True)
subprocess.run(["mount", "-o", "loop,ro", str(overlay_sq), str(mnt_overlay)], check=True)

# Mount overlay
subprocess.run([
    "mount", "-t", "overlay", "overlay",
    "-o", f"lowerdir={mnt_overlay}:{mnt_base},upperdir={upper},workdir={work}",
    str(merged)
], check=True)

try:
    print("Testing mktemp:")
    p = subprocess.run(["chroot", str(merged), "mktemp", "-dt", "debconf.XXXXXX"], capture_output=True, text=True)
    print("mktemp rc:", p.returncode, "stdout:", p.stdout.strip(), "stderr:", p.stderr.strip())
    debconf_dir = p.stdout.strip()

    if debconf_dir:
        # copy config.dat & passwords.dat
        print("Checking /var/cache/debconf/config.dat:")
        cfg_dat = merged / "var" / "cache" / "debconf" / "config.dat"
        print("Exists:", cfg_dat.exists())

        print("Testing debconf-communicate:")
        p2 = subprocess.run([
            "chroot", str(merged), "debconf-communicate", "-fnoninteractive", "casper"
        ], input="GET casper/username\n", capture_output=True, text=True)
        print("debconf-communicate rc:", p2.returncode, "stdout:", p2.stdout.strip(), "stderr:", p2.stderr.strip())
finally:
    subprocess.run(["umount", str(merged)], check=False)
    subprocess.run(["umount", str(mnt_overlay)], check=False)
    subprocess.run(["umount", str(mnt_base)], check=False)
