# PyFlare Store

**ID:** `dev.pyflare.Store`
**Technology:** Python/GTK4
**Description:** Application and extension marketplace
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
store/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/store
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
