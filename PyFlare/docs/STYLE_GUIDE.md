# PyFlare OS Style Guide

## Python

- Python 3.12+
- PEP 8, max line length 100
- Type hints on all public functions
- Docstrings on all modules and public classes
- Linter: `ruff`

## Shell Scripts

- `#!/usr/bin/env bash`
- `set -euo pipefail` at top
- `shellcheck` must pass at `--severity=warning`
- Quote all variables: `"$VAR"`

## YAML / JSON

- 2-space indent
- Keys in `snake_case`
- No trailing spaces

## .desktop Files

- Follow [freedesktop.org spec](https://specifications.freedesktop.org/desktop-entry-spec/latest/)
- Always include: `Name`, `Type`, `Exec`, `Icon`, `Categories`
- Use `dev.pyflare.{App}` naming for `Icon` and `StartupWMClass`
- `Categories` must include `PyFlare;`

## File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Python modules | `snake_case.py` | `validate_icons.py` |
| Shell scripts | `snake_case.sh` | `post_install.sh` |
| Config files | `snake_case.yaml` | `default.yaml` |
| Desktop entries | `dev.pyflare.App.desktop` | `dev.pyflare.Terminal.desktop` |
| Systemd units | `pyflare-name.service` | `pyflare-engine.service` |

## Commit Messages

```
type(scope): short description

Longer explanation if needed.
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
Scopes: `branding`, `filesystem`, `desktop`, `installer`, `apps`, `validation`, `ci`

Example: `feat(desktop): add PyFlare-Dark GNOME Shell theme`
