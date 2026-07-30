# PyFlare Launcher

**ID:** `dev.pyflare.Launcher`
**Technology:** Python/GTK4
**Description:** Application launcher with AI suggestions
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
launcher/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/launcher
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
