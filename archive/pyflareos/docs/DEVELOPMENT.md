# Development Guide

## Repository Layout

```
PyFlare/
├── branding/              Generated assets (do not edit manually)
├── branding_generator/    Asset generator (Python)
├── config/                Build configuration
├── filesystem/            Linux filesystem source tree
├── desktop/               GNOME desktop overrides
├── packages/              Package manifests
├── installer/             Calamares config
├── applications/          App source stubs
├── validation/            Automated validators
├── scripts/               Build scripts
├── docs/                  Documentation
└── tests/                 Test suite
```

## Prerequisites

```bash
pip install -r requirements.txt
```

## Common Tasks

### Regenerate all branding
```bash
python -m branding_generator.main generate
python -m branding_generator.main validate
python scripts/copy_branding.py
```

### Run all validators
```bash
python validation/run_all.py
```

### Add a new application
1. Create `applications/{slug}/` with standard structure
2. Add `.desktop` file to `filesystem/usr/share/applications/`
3. Add to `config/branding.yaml` applications section
4. Add to `packages/manifests/applications.json`
5. Update `validation/validate_desktop_entries.py` DESKTOP_APP_IDS list

### Modify filesystem config
Edit files in `filesystem/etc/` or `filesystem/usr/share/`.
Run `python scripts/prepare_rootfs.py` to rebuild the overlay.

## Code Style

- Python: follow PEP 8, max line length 100
- Use `ruff` for linting: `ruff check .`
- Shell: use `shellcheck`
- YAML: 2-space indent, use `yamllint`
