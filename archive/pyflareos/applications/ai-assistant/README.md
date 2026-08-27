# AI Assistant

**ID:** `dev.pyflare.AIAssistant`
**Technology:** Python
**Description:** On-device AI assistant powered by Ollama
**Version:** 1.0.0
**Vendor:** Aachman Studios

## Structure

```
ai-assistant/
├── src/          Application source code
├── assets/       Icons, images, UI resources
├── desktop/      .desktop and autostart files
├── config/       Default configuration
└── tests/        Unit and integration tests
```

## Running in Development

```bash
cd applications/ai-assistant
python src/main.py --dev
```

## Installing

Handled automatically by `scripts/package_apps.py` during build.
