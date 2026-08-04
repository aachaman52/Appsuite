# AppSuite Ecosystem — Documentation Hub

**Version:** 1.0.0 | **Organisation:** Aachman Studios | **Last Updated:** 2026-08-04

> *"The AI-Native Linux Distribution and Autonomous Engineering Engine"*

---

## What Is This Repository?

This repository contains the full source and documentation for the **AppSuite Ecosystem** — a unified platform consisting of three interconnected projects:

| Sub-project | Type | Description |
|---|---|---|
| **PyFlare OS** (`PyFlare/`) | Operating System | Custom Ubuntu 24.04 LTS derivative with AI-native tooling, procedural branding, and a developer-optimised GNOME desktop |
| **AppSuite Jarvis** (`AppSuite_JarvisV1/`) | AI Engine | Autonomous multi-agent software engineering system with DAG execution, 4-tier memory, and a FastAPI dashboard |
| **LangGraph** (`langgraph-main/`) | Runtime | Vendored LangGraph library providing StateGraph primitives for Jarvis agent orchestration |

---

## Documentation Index

### Core Documentation

| Document | Description |
|---|---|
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | Non-technical overview of the entire ecosystem |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full technical architecture with diagrams |
| [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md) | Complete annotated file tree |
| [REPOSITORY_WALKTHROUGH.md](REPOSITORY_WALKTHROUGH.md) | Guided walkthrough: how everything connects |

### Build & Deployment

| Document | Description |
|---|---|
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | ISO build system reference |
| [BOOT_PROCESS.md](BOOT_PROCESS.md) | Boot sequence from firmware to desktop |
| [INSTALLER.md](INSTALLER.md) | Calamares installer configuration |
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | Release workflow and versioning |
| [VERSIONING.md](VERSIONING.md) | Versioning strategy |

### AI & Engine

| Document | Description |
|---|---|
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | AppSuite Jarvis engine deep-dive |
| [ENGINE.md](ENGINE.md) | Graph orchestrator and DAG execution |
| [ORCHESTRATION.md](ORCHESTRATION.md) | Multi-agent coordination |
| [PLUGIN_SYSTEM.md](PLUGIN_SYSTEM.md) | Jarvis plugin SDK |

### OS Components

| Document | Description |
|---|---|
| [BRANDING.md](BRANDING.md) | Visual identity and branding generator |
| [FILESYSTEM.md](FILESYSTEM.md) | Filesystem overlay structure |
| [PACKAGE_SYSTEM.md](PACKAGE_SYSTEM.md) | APT/Flatpak/Snap package management |
| [NETWORKING.md](NETWORKING.md) | Network stack and configuration |
| [SECURITY.md](SECURITY.md) | Security model and hardening |
| [APPLICATION_FRAMEWORK.md](APPLICATION_FRAMEWORK.md) | Bundled application architecture |

### Development

| Document | Description |
|---|---|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developer environment setup |
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code style and standards |
| [STYLE_GUIDE.md](STYLE_GUIDE.md) | Documentation and visual style guide |
| [API_GUIDELINES.md](API_GUIDELINES.md) | API design guidelines |
| [TESTING.md](TESTING.md) | Test suite and validation |

### Project Management

| Document | Description |
|---|---|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current completion dashboard |
| [CHECKLIST.md](CHECKLIST.md) | Full project task checklist |
| [TODO.md](TODO.md) | Active task queue |
| [BACKLOG.md](BACKLOG.md) | Feature backlog |
| [MILESTONES.md](MILESTONES.md) | Milestones and roadmap |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Known bugs and limitations |
| [TECH_DEBT.md](TECH_DEBT.md) | Technical debt register |
| [CHANGELOG_GUIDE.md](CHANGELOG_GUIDE.md) | How to write changelogs |

---

## Quick Start

### Build PyFlare OS (Linux only)

```bash
# Clone the repository
git clone https://github.com/aachaman52/Appsuite.git
cd Appsuite/PyFlare

# Install Python dependencies
pip install -r requirements.txt

# Generate all branding assets
python -m branding_generator.main generate

# Validate assets
python validation/run_all.py

# Build ISO (requires Linux, sudo, squashfs-tools, xorriso)
sudo python3 build.py --config config/default.yaml
```

### Run AppSuite Jarvis (Windows/Linux/macOS)

```bash
cd Appsuite/AppSuite_JarvisV1

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure API keys in .env
cp .env.example .env

# Start the Jarvis server
python -m appsuite
```

---

## Repository Statistics

| Metric | Value |
|---|---|
| Total files | ~1,866 |
| Total directories | ~545 |
| Python source files | 731 |
| Markdown documents | 94 |
| Branding asset categories | 24 |
| Generated branding assets | 800+ |
| Application stubs | 11 |
| Build scripts | 22 |
| Validators | 14 |
| AI agents | 6+ specialized |
| Execution workers | 8 |
| Intelligence modules (core/) | 44 |
| LLM providers supported | 5 (NVIDIA NIM, OpenAI, Gemini, Claude, Ollama) |
| Repository size (excl. squashfs) | ~200 MB |

---

## Supported Platforms

| Platform | Role | Status |
|---|---|---|
| Ubuntu 24.04 LTS | Build host (required for ISO build) | ✅ Supported |
| Windows 10/11 | Development (AppSuite Jarvis, branding generator) | ✅ Supported |
| macOS 13+ | Development (AppSuite Jarvis) | ✅ Supported |
| PyFlare OS | Primary deployment target | 🟡 In progress |

---

## Licence

- **PyFlare OS**: Proprietary — Aachman Studios. See `PyFlare/LICENSE`.
- **AppSuite Jarvis**: MIT Licence. See `AppSuite_JarvisV1/LICENSE`.
- **LangGraph**: MIT Licence. See `langgraph-main/LICENSE`.
- Component licences (Ubuntu, GNOME, GTK, Mesa, etc.) remain with their respective owners.

---

*Built with ❤️ by Aachman Studios — Founder: Aachman Harlalka*
