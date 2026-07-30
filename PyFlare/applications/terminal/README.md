# PyFlare Terminal

**ID:** `dev.pyflare.Terminal`
**Technology:** Python/VTE
**Description:** GPU-accelerated AI-assisted terminal
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
terminal/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/terminal
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
