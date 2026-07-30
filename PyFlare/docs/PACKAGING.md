# PyFlare OS Packaging

## Package Naming

`pyflare-{component}_{version}_all.deb`

## Core Packages

| Package | Description |
|---------|-------------|
| `pyflare-engine` | Runtime daemon |
| `pyflare-desktop` | Theme + icons + wallpapers |
| `pyflare-apps` | Meta-package (all apps) |
| `pyflare-fonts` | Inter + Space Grotesk + JetBrains Mono |
| `pyflare-cursors` | Custom cursor theme |

## Manifests

Package manifests live in `packages/manifests/`.
Format: JSON with `schema: pyflare-package-manifest/1.0`.

## Build

```bash
# Package all applications
python scripts/package_apps.py

# Generate filesystem manifest
python scripts/generate_manifest.py
```
