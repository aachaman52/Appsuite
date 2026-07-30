# PyFlare OS Package Structure

| Directory | Purpose |
|-----------|---------|
| `manifests/` | JSON package manifests |
| `metadata/` | Per-package metadata and changelogs |
| `scripts/` | Install/remove hook scripts |

## Package Naming Convention

`pyflare-{component}_{version}_all.deb`

- `pyflare-engine` — Core engine
- `pyflare-desktop` — Theme, icons, wallpapers
- `pyflare-apps` — Meta-package for all apps
- `pyflare-{appname}` — Individual applications
