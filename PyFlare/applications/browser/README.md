# PyFlare Browser

**ID:** `dev.pyflare.Browser`
**Technology:** Python/WebKit
**Description:** Privacy-focused web browser
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
browser/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/browser
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
