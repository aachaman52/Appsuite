# Package Manager

**ID:** `dev.pyflare.PackageManager`
**Technology:** Python/GTK4
**Description:** Unified APT, Flatpak, and Snap manager
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
package-manager/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/package-manager
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
