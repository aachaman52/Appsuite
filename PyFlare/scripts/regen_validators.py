#!/usr/bin/env python3
"""Regenerate all validator files with correct indentation."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL  = os.path.join(ROOT, "validation")
os.makedirs(VAL, exist_ok=True)

VALIDATORS = {
"validate_branding": """\
import os

def validate(root):
    errors = []
    branding = os.path.join(root, 'branding')
    if not os.path.isdir(branding):
        return False, ['branding/ directory missing']
    required = ['logos/svg', 'wallpapers', 'cursors', 'badges', 'previews']
    for r in required:
        if not os.path.isdir(os.path.join(branding, r)):
            errors.append(f'Missing branding/{r}/')
    return len(errors) == 0, errors
""",

"validate_icons": """\
import os

def validate(root):
    errors = []
    idx = os.path.join(root, 'filesystem/usr/share/icons/PyFlare-Icons/index.theme')
    if not os.path.exists(idx):
        errors.append('PyFlare-Icons/index.theme missing')
    return len(errors) == 0, errors
""",

"validate_wallpapers": """\
import os

def validate(root):
    errors = []
    bg = os.path.join(root, 'filesystem/usr/share/backgrounds/pyflare')
    if not os.path.isdir(bg):
        errors.append('backgrounds/pyflare/ missing -- run copy_branding.py')
    return len(errors) == 0, errors
""",

"validate_json": """\
import os
import json

def validate(root):
    errors = []
    skip = {'.git', 'node_modules', '__pycache__', 'branding'}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not fname.endswith('.json'):
                continue
            fp = os.path.join(dirpath, fname)
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    json.load(fh)
            except Exception as exc:
                errors.append(f"{os.path.relpath(fp, root)}: {exc}")
    return len(errors) == 0, errors
""",

"validate_svg": """\
import os
import xml.etree.ElementTree as ET

def validate(root):
    errors = []
    skip = {'.git', '__pycache__'}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            if not fname.endswith('.svg'):
                continue
            fp = os.path.join(dirpath, fname)
            try:
                ET.parse(fp)
            except Exception as exc:
                errors.append(f"{os.path.relpath(fp, root)}: {exc}")
    return len(errors) == 0, errors
""",

"validate_desktop": """\
import os

REQUIRED_KEYS = ['Type', 'Name', 'Exec', 'Icon']

def validate(root):
    errors = []
    apps_dir = os.path.join(root, 'filesystem/usr/share/applications')
    if not os.path.isdir(apps_dir):
        return False, ['filesystem/usr/share/applications/ missing']
    for fname in os.listdir(apps_dir):
        if not fname.endswith('.desktop'):
            continue
        fp = os.path.join(apps_dir, fname)
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
        for key in REQUIRED_KEYS:
            if f'{key}=' not in content:
                errors.append(f"{fname}: missing {key}")
    return len(errors) == 0, errors
""",

"validate_packages": """\
import os
import json

def validate(root):
    errors = []
    manifests = os.path.join(root, 'packages/manifests')
    if not os.path.isdir(manifests):
        return False, ['packages/manifests/ missing']
    for fname in os.listdir(manifests):
        if not fname.endswith('.json'):
            continue
        fp = os.path.join(manifests, fname)
        try:
            with open(fp) as fh:
                data = json.load(fh)
            if 'schema' not in data:
                errors.append(f"{fname}: missing schema field")
        except Exception as exc:
            errors.append(f"{fname}: {exc}")
    return len(errors) == 0, errors
""",

"validate_filesystem": """\
import os

REQUIRED = [
    'etc/hostname', 'etc/os-release', 'etc/fstab', 'etc/hosts',
    'etc/environment', 'etc/default/grub', 'etc/gdm3/custom.conf',
    'etc/systemd/system/pyflare-engine.service',
    'etc/systemd/system/pyflare-firstrun.service',
    'etc/pyflare/os.conf',
    'usr/share/applications',
    'usr/share/glib-2.0/schemas/99-pyflare.gschema.override',
]

def validate(root):
    errors = []
    fs = os.path.join(root, 'filesystem')
    for r in REQUIRED:
        if not os.path.exists(os.path.join(fs, r)):
            errors.append(f"filesystem/{r} missing")
    return len(errors) == 0, errors
""",

"validate_theme": """\
import os

REQUIRED_THEME_FILES = [
    'index.theme',
    'gtk-3.0/gtk.css',
    'gtk-4.0/gtk.css',
    'gnome-shell/gnome-shell.css',
]

def validate(root):
    errors = []
    theme = os.path.join(root, 'filesystem/usr/share/themes/PyFlare-Dark')
    if not os.path.isdir(theme):
        return False, ['PyFlare-Dark theme directory missing']
    for rel in REQUIRED_THEME_FILES:
        fp = os.path.join(theme, rel)
        if not os.path.exists(fp):
            errors.append(f"PyFlare-Dark/{rel} missing")
        elif os.path.getsize(fp) < 10:
            errors.append(f"PyFlare-Dark/{rel} is empty")
    return len(errors) == 0, errors
""",

"validate_configs": """\
import os
try:
    import yaml
except ImportError:
    yaml = None

REQUIRED = ['default.yaml', 'packages.yaml', 'theme.yaml', 'branding.yaml', 'post_install.sh']

def validate(root):
    errors = []
    cfg = os.path.join(root, 'config')
    for fname in REQUIRED:
        fp = os.path.join(cfg, fname)
        if not os.path.exists(fp):
            errors.append(f"config/{fname} missing")
        elif yaml and fname.endswith('.yaml'):
            try:
                with open(fp) as fh:
                    yaml.safe_load(fh)
            except Exception as exc:
                errors.append(f"config/{fname}: YAML error: {exc}")
    return len(errors) == 0, errors
""",

"validate_services": """\
import os
import configparser

REQUIRED_SERVICES = [
    'pyflare-engine.service',
    'pyflare-firstrun.service',
    'pyflare-update.service',
    'pyflare-update.timer',
]

def validate(root):
    errors = []
    svc_dir = os.path.join(root, 'filesystem/etc/systemd/system')
    for svc in REQUIRED_SERVICES:
        fp = os.path.join(svc_dir, svc)
        if not os.path.exists(fp):
            errors.append(f"systemd/{svc} missing")
        else:
            c = configparser.ConfigParser(strict=False)
            try:
                c.read(fp)
                if not c.has_section('Unit'):
                    errors.append(f"{svc}: missing [Unit] section")
            except Exception as exc:
                errors.append(f"{svc}: {exc}")
    return len(errors) == 0, errors
""",

"validate_permissions": """\
import os
import stat

ADVISORY = [
    'opt/pyflare/engine/pyflare-engine',
    'opt/pyflare/bin/pyflare-updater',
    'opt/pyflare/bin/pyflare-firstrun',
]

def validate(root):
    warnings = []
    fs = os.path.join(root, 'filesystem')
    for rel in ADVISORY:
        fp = os.path.join(fs, rel)
        if os.path.exists(fp) and not (os.stat(fp).st_mode & stat.S_IXUSR):
            warnings.append(f"{rel} not executable (fixable at install)")
    return True, warnings
""",

"validate_desktop_entries": """\
import os

DESKTOP_APP_IDS = [
    'dev.pyflare.Engine', 'dev.pyflare.AppSuite', 'dev.pyflare.Terminal',
    'dev.pyflare.Browser', 'dev.pyflare.Files', 'dev.pyflare.Store',
    'dev.pyflare.Settings', 'dev.pyflare.PackageManager',
    'dev.pyflare.PluginManager', 'dev.pyflare.Launcher', 'dev.pyflare.AIAssistant',
]

def validate(root):
    errors = []
    apps_dir = os.path.join(root, 'filesystem/usr/share/applications')
    for app_id in DESKTOP_APP_IDS:
        fp = os.path.join(apps_dir, f'{app_id}.desktop')
        if not os.path.exists(fp):
            errors.append(f'{app_id}.desktop missing')
    return len(errors) == 0, errors
""",

"validate_boot": """\
import os

REQUIRED_BOOT = [
    'etc/default/grub',
    'etc/plymouth/plymouthd.conf',
    'boot/grub/themes/pyflare/theme.txt',
    'usr/share/plymouth/themes/pyflare/pyflare.plymouth',
    'usr/share/plymouth/themes/pyflare/pyflare.script',
]

def validate(root):
    errors = []
    fs = os.path.join(root, 'filesystem')
    for rel in REQUIRED_BOOT:
        if not os.path.exists(os.path.join(fs, rel)):
            errors.append(f"filesystem/{rel} missing")
    return len(errors) == 0, errors
""",
}

FOOTER_TPL = """

if __name__ == '__main__':
    _root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ok, _errors = validate(_root)
    for _e in _errors:
        print(f'  [error] {{_e}}')
    print(f'  {{"PASS" if _ok else "FAIL"}}: {name}')
    sys.exit(0 if _ok else 1)
"""

for name, body in VALIDATORS.items():
    header = f'#!/usr/bin/env python3\n"""validation/{name}.py — PyFlare OS validator"""\nimport os\nimport sys\n\n'
    footer = FOOTER_TPL.format(name=name)
    content = header + body.strip() + "\n" + footer
    path = os.path.join(VAL, f"{name}.py")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"  [ok] {name}.py")

print("All validators written.")
