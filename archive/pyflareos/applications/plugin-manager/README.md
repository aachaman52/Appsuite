# Plugin Manager

**ID:** `dev.pyflare.PluginManager`
**Technology:** Python/GTK4
**Description:** Manage PyFlare Engine plugins
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
plugin-manager/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/plugin-manager
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
