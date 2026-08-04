# AppSuite Ecosystem — Security

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Overview

This document covers the security model for both PyFlare OS and AppSuite Jarvis.

---

## PyFlare OS Security

### Base System Hardening

| Measure | Status |
|---|---|
| Ubuntu security backports | ✅ Inherited from Ubuntu 24.04 |
| UFW firewall | ✅ Installed and enabled |
| nftables | ✅ Installed |
| AppArmor | ✅ Active (Ubuntu default) |
| Secure Boot | 🔴 Planned for v2.0.0 (Ignite) |
| Automatic security updates | 🟡 Planned for v1.2.0 (Nova) |

### Network

OpenSSH server is installed but disabled by default. Enable only when needed:

```bash
sudo systemctl enable --now ssh
```

UFW default policy: deny incoming, allow outgoing.

### User Accounts

Default build creates a `pyflare` user (non-root). The installer creates a new user account during installation — the `pyflare` user is replaced.

### API Key Handling (Jarvis)

API keys are stored in `.env` files which are:
- Listed in `.gitignore` (never committed)
- Read at runtime via `python-dotenv`
- Never logged or exposed in API responses

### Reporting Vulnerabilities

Report security issues via: `hello@aachmanstudios.dev`

Do not open public GitHub issues for security vulnerabilities.

---

## AppSuite Jarvis Security

### Worker Sandboxing

Workers that invoke external processes (Blender, Godot) run as subprocesses with:
- Controlled environment variables
- Timeout enforcement (5 minutes per task)
- Output capture (stdout/stderr) — not exec-in-shell

### Code Worker Caution

`CodeWorker` generates code via LLM. Generated code is written to disk but **not automatically executed** — it must be explicitly invoked. The self-healing loop validates generated code via `ValidationWorker` before deployment.

### Database

SQLite database (`data/appsuite.db`) contains job history, memory, and knowledge graph. It is local-only — no network exposure. Keep it out of version control.

### API Authentication

The FastAPI server currently has no authentication (development mode). Before exposing to a network, add authentication middleware or restrict to `localhost`.

---

## Related Documents

| Document | Purpose |
|---|---|
| [NETWORKING.md](NETWORKING.md) | Network stack and configuration |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Developer setup |
