# PyFlare OS Build Checklist

This checklist must be verified before executing `python build.py` on a production Linux host.

## 1. Host Preparation
- [ ] Host is running Ubuntu 24.04 LTS natively or via robust virtualization.
- [ ] Root access is available.
- [ ] `scripts/install_dependencies.sh` has been executed successfully.
- [ ] Host has at least 15 GB of free disk space.
- [ ] Host has at least 8 GB of RAM.

## 2. Configuration Validation
- [ ] `config/packages.yaml` is syntactically valid and dependencies are resolvable on Ubuntu 24.04.
- [ ] All required branding assets (Plymouth, GRUB, GTK themes, icons) are present in `branding/` or `filesystem/`.

## 3. Build Execution
- [ ] `python3 build.py` completes without any `[FAIL]` stages.
- [ ] SquashFS generation completes without compression errors.
- [ ] ISO generation (`xorriso`) completes without bootloader errors.

## 4. Artifact Verification
- [ ] `reports/build_report.json` shows status `SUCCESS`.
- [ ] `output/pyflare-os-1.0.0-ember-amd64.iso` exists.
- [ ] `reports/checksums.json` contains the SHA256 of the ISO.
