# PyFlare Engine

**ID:** `dev.pyflare.Engine`
**Technology:** Python
**Description:** AI-native runtime and daemon
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
engine/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/engine
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
