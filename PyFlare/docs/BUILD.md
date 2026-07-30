# Building PyFlare OS

## Prerequisites

Requires a **native Linux environment** (Ubuntu 22.04+ recommended) with root access.
WSL2, a VM, or a Linux machine all work.

```bash
sudo apt install -y \
  squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools python3 python3-pip rsync calamares \
  libcairo2-dev

pip install -r requirements.txt
```

## Build Steps

```bash
# 1. Generate branding assets
python -m branding_generator.main generate
python -m branding_generator.main validate

# 2. Prepare rootfs overlay
python scripts/prepare_rootfs.py

# 3. Run all validators
python validation/run_all.py

# 4. Build ISO (root required)
sudo python3 build.py --config config/default.yaml

# 5. Generate checksums
python scripts/generate_checksums.py
```

## Output

- `output/pyflare-os-1.0.0-ember-amd64.iso`
- `output/pyflare-os-1.0.0-ember-amd64.iso.sha256`
- `output/pyflare-os-1.0.0-ember-amd64.iso.md5`

## Configuration

| File | Purpose |
|------|---------|
| `config/default.yaml` | Main OS settings |
| `config/packages.yaml` | Package lists |
| `config/theme.yaml` | Visual identity |
| `config/branding.yaml` | Product strings |

## Troubleshooting

- **squashfs error:** Must build on native Linux ext4 filesystem
- **grub error:** Ensure `grub-pc-bin` and `grub-efi-amd64-bin` both installed
- **cairosvg error:** `sudo apt install libcairo2-dev` then `pip install cairosvg`
