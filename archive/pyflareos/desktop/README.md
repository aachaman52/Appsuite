# Desktop Integration Files

This directory contains GNOME desktop environment configuration that is
applied during the ISO build process.

| Directory | Purpose |
|-----------|---------|
| `gsettings/` | dconf/gsettings schema overrides |
| `dock/` | Dash-to-Dock extension configuration |
| `menus/` | XDG application menu definitions |
| `autostart/` | Session autostart entries |
| `shortcuts/` | Keyboard shortcut definitions |

## Applying Changes

```bash
python scripts/copy_branding.py --desktop
```
