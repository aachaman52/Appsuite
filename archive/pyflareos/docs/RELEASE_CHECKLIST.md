# PyFlare OS Release Checklist

This checklist governs the transition of an ISO from a successful build to a stable public release.

## 1. Automated Runtime Verification
- [ ] `scripts/verify_runtime.py` executed successfully in QEMU.
- [ ] No kernel panics observed in the boot logs.
- [ ] Boot process completes without entering a boot loop.
- [ ] Systemd initializes `multi-user.target` successfully.

## 2. Interactive QA Testing
- [ ] Boot the ISO via USB on physical UEFI hardware.
- [ ] Verify GRUB displays the PyFlare theme correctly.
- [ ] Verify Plymouth splash animation loads smoothly without tearing.
- [ ] Verify GNOME/GDM starts and automatically logs in to the live session (if configured).
- [ ] Verify NetworkManager starts and connects to Wi-Fi/Ethernet.
- [ ] Open the launcher and verify all 11 packaged PyFlare applications appear with correct icons.
- [ ] Verify custom GTK theme "PyFlare-Dark" and icon theme "PyFlare-Icons" are applied.
- [ ] Run the Calamares installer and complete a full disk installation.

## 3. Post-Installation Verification
- [ ] Boot the newly installed physical system.
- [ ] Verify default user creation succeeded.
- [ ] Open terminal, verify APT package manager works (`apt update`).
- [ ] Verify all PyFlare systemd services are running (`systemctl status pyflare-engine.service`).

## 4. Final Delivery
- [ ] `reports/runtime_report.json` indicates SUCCESS.
- [ ] Calculate the final SHA256 of the ISO and upload it to the release page.
- [ ] Publish the release notes matching `CHANGELOG.md`.
