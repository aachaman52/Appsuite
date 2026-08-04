# AppSuite Ecosystem — Application Framework

**Version:** 1.0.0 | **Status:** Stubs Complete / GTK4 Implementation Planned | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

PyFlare OS bundles 11 application stubs under `PyFlare/applications/`. Each stub provides a `.desktop` launcher, directory structure, and configuration skeleton. Full GTK4 implementations are planned for PyFlare OS v1.1.0 (Flare) and beyond.

---

## Bundled Applications

| App | ID | Description | Status |
|---|---|---|---|
| **AI Assistant** | `dev.pyflare.AIAssistant` | On-device AI chat powered by Ollama | Stub |
| **AppSuite** | `dev.pyflare.AppSuite` | Jarvis IDE integration | Stub (backend complete) |
| **Browser** | `dev.pyflare.Browser` | Privacy-focused WebKit browser | Stub |
| **Engine** | `dev.pyflare.Engine` | PyFlare Engine service daemon | Stub |
| **Files** | `dev.pyflare.Files` | AI-powered file manager | Stub |
| **Launcher** | `dev.pyflare.Launcher` | Application launcher with AI suggest | Stub |
| **Package Manager** | `dev.pyflare.PackageManager` | Unified APT/Flatpak/Snap UI | Stub |
| **Plugin Manager** | `dev.pyflare.PluginManager` | Plugin and extension management | Stub |
| **Settings** | `dev.pyflare.Settings` | System preferences panel | Stub |
| **Store** | `dev.pyflare.Store` | Application and extension marketplace | Stub |
| **Terminal** | `dev.pyflare.Terminal` | GPU-accelerated terminal + AI completions | Stub |

---

## Application Technology Stack (Planned)

| Layer | Technology |
|---|---|
| Framework | GTK 4 + libadwaita |
| Language | Python 3 with PyGObject (`python3-gi`) |
| Bindings | GIR: `gir1.2-gtk-4.0`, `gir1.2-adw-1` |
| Theming | Adwaita (base) + PyFlare-Dark overrides |
| IPC | D-Bus for inter-application communication |
| AI backend | Ollama HTTP API (`localhost:11434`) |
| File manager backend | GIO / GVfs |

---

## Application Directory Structure

Each application stub follows this layout:

```
applications/<app-name>/
├── <app-name>.desktop      XDG desktop entry
├── config/
│   └── settings.yaml       Default application settings
└── assets/
    └── icon.svg            Application icon reference
```

---

## Desktop Integration

Applications are integrated via:

1. **XDG .desktop files** in `filesystem/usr/share/applications/` — appear in GNOME Activities and application menus
2. **Autostart entries** in `desktop/autostart/` for background services (Engine, AI Assistant daemon)
3. **MIME type handlers** registered for relevant file formats
4. **D-Bus services** for IPC with the system

---

## AI Assistant — Architecture Note

The AI Assistant stub is backed by **Ollama** installed at the OS level. The planned implementation:

```
AI Assistant UI (GTK4 + libadwaita)
        ↓ HTTP
Ollama (localhost:11434)
        ↓
Local model (llama3 or custom-pulled model)
```

No API keys required. Everything runs on-device. For cloud fallback, `AppSuite Jarvis` provides the ProviderManager with multi-provider support.

---

## AppSuite Application — Architecture Note

The `AppSuite` application is the most developed stub — its backend (`AppSuite_JarvisV1/`) is fully implemented. The stub connects the OS launcher to the Jarvis FastAPI server at `localhost:8000`.

Planned UI: a GTK4 + libadwaita IDE-like window with:
- Prompt input panel
- Real-time job progress (EventBus → WebSocket → UI)
- Asset browser
- Project workspace view
- Agent activity log

---

## Related Documents

| Document | Purpose |
|---|---|
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | AppSuite Jarvis engine |
| [FILESYSTEM.md](FILESYSTEM.md) | Where app files are installed |
| [BRANDING.md](BRANDING.md) | Application icons and theming |
| [MILESTONES.md](MILESTONES.md) | GTK4 implementation roadmap |
