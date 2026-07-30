# PyFlare Settings

**ID:** `dev.pyflare.Settings`
**Technology:** Python/GTK4
**Description:** System configuration and preferences
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
settings/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/settings
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
