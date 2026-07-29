import os
import json
import logging
from branding_generator.config import THEME_SCHEMES, BRAND_COLORS
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def generate_color_files(branding_dir):
    colors_dir = os.path.join(branding_dir, "colors")
    ensure_dir(colors_dir)
    
    # Save colors.json
    with open(os.path.join(colors_dir, "colors.json"), "w") as f:
        json.dump(BRAND_COLORS, f, indent=2)
        
    # Save colors.css
    css_content = ":root {\n"
    for name, hex_val in BRAND_COLORS.items():
        css_content += f"  --pf-{name}: {hex_val};\n"
    css_content += "}\n"
    with open(os.path.join(colors_dir, "colors.css"), "w") as f:
        f.write(css_content)
        
    # Save colors.scss
    scss_content = ""
    for name, hex_val in BRAND_COLORS.items():
        scss_content += f"$pf-{name}: {hex_val};\n"
    with open(os.path.join(colors_dir, "colors.scss"), "w") as f:
        f.write(scss_content)
        
    # Save colors.qml
    qml_content = "import QtQuick 2.15\n\nQtObject {\n"
    for name, hex_val in BRAND_COLORS.items():
        qml_content += f"    readonly property color {name}: \"{hex_val}\"\n"
    qml_content += "}\n"
    with open(os.path.join(colors_dir, "colors.qml"), "w") as f:
        f.write(qml_content)
        
    # Save colors.toml
    toml_content = "[colors]\n"
    for name, hex_val in BRAND_COLORS.items():
        toml_content += f"{name} = \"{hex_val}\"\n"
    with open(os.path.join(colors_dir, "colors.toml"), "w") as f:
        f.write(toml_content)
        
    # Save colors.yaml
    yaml_content = "colors:\n"
    for name, hex_val in BRAND_COLORS.items():
        yaml_content += f"  {name}: \"{hex_val}\"\n"
    with open(os.path.join(colors_dir, "colors.yaml"), "w") as f:
        f.write(yaml_content)

def generate_desktop_themes(branding_dir):
    themes_dir = os.path.join(branding_dir, "themes")
    ensure_dir(themes_dir)
    
    # Write JSON theme sheets
    for scheme_name, scheme_data in THEME_SCHEMES.items():
        with open(os.path.join(themes_dir, f"{scheme_name}_theme.json"), "w") as f:
            json.dump(scheme_data, f, indent=2)
            
    # Generate GTK (CSS) and Terminal configuration placeholders
    gtk_dir = os.path.join(themes_dir, "gtk")
    ensure_dir(gtk_dir)
    gtk_css = f'''@import url("colors.css");
window {{
  background-color: {BRAND_COLORS["background"]};
  color: {BRAND_COLORS["white"]};
}}
button {{
  background-color: {BRAND_COLORS["surface"]};
  border-radius: 8px;
  border: 1px solid {BRAND_COLORS["indigo"]};
}}
button:hover {{
  background-color: {BRAND_COLORS["primary"]};
}}
'''
    with open(os.path.join(gtk_dir, "gtk.css"), "w") as f:
        f.write(gtk_css)
        
    # Generate VS Code theme json
    vscode_theme = {
        "name": "PyFlare Dark VSCode",
        "type": "dark",
        "colors": {
            "editor.background": BRAND_COLORS["background"],
            "editor.foreground": BRAND_COLORS["white"],
            "sideBar.background": BRAND_COLORS["surface"],
            "activityBar.background": BRAND_COLORS["background"],
            "statusBar.background": BRAND_COLORS["indigo"]
        }
    }
    with open(os.path.join(themes_dir, "vscode_theme.json"), "w") as f:
        json.dump(vscode_theme, f, indent=2)

def generate_all_themes(target_root):
    generate_color_files(target_root)
    generate_desktop_themes(target_root)
    logger.info("Successfully generated colors configuration and desktop/GTK themes")
