# AppSuite Ecosystem — Feature Backlog

**Version:** 1.0.0 | **Last Updated:** 2026-08-04 | **Author:** Aachman Studios

Planned features not yet in active development. Ordered by target milestone.

---

## v1.1.0 Flare — PyFlare OS

| Feature | Description | Dependencies |
|---|---|---|
| PyFlare Engine (real) | Full daemon integrating Jarvis API | AppSuite GTK4 UI |
| AppSuite GTK4 IDE | Prompt input + job progress + workspace view | Jarvis FastAPI |
| PyFlare Terminal | VTE-based terminal with AI completions (Ollama) | Ollama live test |
| PyFlare Store | Flatpak frontend with PyFlare branding | Flatpak |
| Plymouth animated flame | Rendered video sequence replacing script animation | Linux build |
| GRUB custom background | Rendered background image in GRUB theme | branding generator |
| Calamares installer images | Real screenshots in installer slides | Live ISO boot |
| Ollama model manager | GUI for downloading/managing local AI models | AppSuite GTK4 |

---

## v1.2.0 Nova — PyFlare OS

| Feature | Description |
|---|---|
| PyFlare Files | GTK4 file manager with Ollama semantic search |
| PyFlare Browser | WebKitGTK-based privacy browser |
| Plugin system (OS level) | Load/unload plugins from PyFlare Store |
| Automatic security updates | Unattended-upgrades for security patches |
| OEM configuration support | White-label support for other vendors |
| Offline documentation | Built-in offline docs viewer |
| Accessibility improvements | Screen reader, high contrast theme |

---

## v2.0.0 Ignite — PyFlare OS

| Feature | Description |
|---|---|
| KDE Plasma edition | Optional KDE desktop alongside GNOME |
| ARM64 support | aarch64 ISO build |
| Secure Boot | Shim + signing |
| Immutable root | Read-only squashfs + overlayfs for system |
| Flatpak-first model | System apps via Flatpak |
| Live USB persistence | Persistent storage on live USB |

---

## Jarvis Phase 12+ Backlog

| Phase | Feature | Description |
|---|---|---|
| 12 | Cloud architecture | Hosted Jarvis endpoint, multi-tenant |
| 13 | Distributed agents | Agents across multiple machines/nodes |
| 14 | AppSuite Marketplace | Plugin and template store |
| 15 | Autonomous Company Builder | Multi-project, multi-team orchestration |

---

## Long-Term Research Items

| Item | Description |
|---|---|
| Fine-tuning pipeline | Custom model fine-tuning on project-specific code |
| Code execution sandbox | Safe execution of LLM-generated code in Docker |
| Vision agent | Screenshot-based UI validation |
| Multi-modal input | Accept images/diagrams as part of the goal prompt |
| Persistent world model | Cross-session project state without re-analysis |

---

## Related Documents

| Document | Purpose |
|---|---|
| [MILESTONES.md](MILESTONES.md) | Milestone targets |
| [TODO.md](TODO.md) | Active tasks |
| [TECH_DEBT.md](TECH_DEBT.md) | Technical debt |
