# AppSuite

**ID:** `dev.pyflare.AppSuite`
**Technology:** Python/GTK4
**Description:** Integrated development and productivity suite
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
appsuite/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/appsuite
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
