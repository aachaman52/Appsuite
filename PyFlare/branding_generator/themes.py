"""
branding_generator/themes.py
Complete theme engine for PyFlare.

Generates:
  colors/
    colors.json, colors.css, colors.scss, colors.qml, colors.toml, colors.yaml

  themes/
    dark_theme.json, light_theme.json, midnight_theme.json
    gtk/gtk.css, gtk/gtk4.css
    qt/pyflare.qss
    kde/PyFlare.colors
    terminal/alacritty.toml, terminal/windows_terminal.json, terminal/gnome.dconf
    vscode/PyFlare-color-theme.json
"""

import os
import json
import logging

from branding_generator.config import BRAND_COLORS, THEME_SCHEMES, GRADIENT_DEFINITIONS, TYPOGRAPHY
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")


# ---------------------------------------------------------------------------
# Color system files
# ---------------------------------------------------------------------------

def generate_color_files(branding_dir: str):
    colors_dir = ensure_dir(os.path.join(branding_dir, "colors"))

    # Enriched JSON with all colours + gradients
    colors_data = {
        "brand": BRAND_COLORS,
        "gradients": GRADIENT_DEFINITIONS,
        "typography": TYPOGRAPHY,
    }
    with open(os.path.join(colors_dir, "colors.json"), "w") as f:
        json.dump(colors_data, f, indent=2)

    # CSS custom properties
    css_lines = [":root {"]
    for name, val in BRAND_COLORS.items():
        css_lines.append(f"  --pf-{name}: {val};")
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        stops = ", ".join(f"{s['color']} {s['offset']}" for s in gdef["stops"])
        if gdef["type"] == "linear":
            css_lines.append(f"  --pf-{gname}: linear-gradient({gdef.get('angle', 135)}deg, {stops});")
        else:
            css_lines.append(f"  --pf-{gname}: radial-gradient(circle, {stops});")
    css_lines.append("}")
    # Per-theme CSS blocks
    for scheme_name, scheme in THEME_SCHEMES.items():
        css_lines.append(f"\n[data-theme=\"{scheme_name}\"] {{")
        for key, val in scheme.items():
            if isinstance(val, str) and key not in ("name", "variant", "font_family",
                                                      "font_heading", "font_mono"):
                css_lines.append(f"  --pf-{key.replace('_', '-')}: {val};")
        css_lines.append("}")
    with open(os.path.join(colors_dir, "colors.css"), "w") as f:
        f.write("\n".join(css_lines) + "\n")

    # SCSS
    scss_lines = ["// PyFlare Brand Colors", "// Auto-generated — do not edit manually", ""]
    for name, val in BRAND_COLORS.items():
        scss_lines.append(f"$pf-{name}: {val};")
    scss_lines.append("\n// Gradient map")
    scss_lines.append("$pf-gradients: (")
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        stops = ", ".join(f"{s['color']} {s['offset']}" for s in gdef["stops"])
        if gdef["type"] == "linear":
            scss_lines.append(f'  "{gname}": linear-gradient({gdef.get("angle", 135)}deg, {stops}),')
        else:
            scss_lines.append(f'  "{gname}": radial-gradient(circle, {stops}),')
    scss_lines.append(");")
    scss_lines.append("\n// Theme maps")
    for scheme_name, scheme in THEME_SCHEMES.items():
        scss_lines.append(f"\n$pf-theme-{scheme_name}: (")
        for key, val in scheme.items():
            if isinstance(val, str):
                scss_lines.append(f'  "{key}": "{val}",')
        scss_lines.append(");")
    with open(os.path.join(colors_dir, "colors.scss"), "w") as f:
        f.write("\n".join(scss_lines) + "\n")

    # QML
    qml_lines = ['import QtQuick 2.15', '', 'QtObject {']
    for name, val in BRAND_COLORS.items():
        qml_lines.append(f'    readonly property color {name}: "{val}"')
    qml_lines.append('')
    qml_lines.append('    // Gradients (as string descriptors)')
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        stops_str = ";".join(f"{s['offset']}={s['color']}" for s in gdef["stops"])
        qml_lines.append(f'    readonly property string {gname}: "{gdef["type"]}:{stops_str}"')
    qml_lines.append('}')
    with open(os.path.join(colors_dir, "colors.qml"), "w") as f:
        f.write("\n".join(qml_lines) + "\n")

    # TOML
    toml_lines = ['[colors]']
    for name, val in BRAND_COLORS.items():
        toml_lines.append(f'{name} = "{val}"')
    toml_lines.append('\n[gradients]')
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        stops = "|".join(f"{s['offset']}:{s['color']}" for s in gdef["stops"])
        toml_lines.append(f'{gname} = "{gdef["type"]}|{stops}"')
    with open(os.path.join(colors_dir, "colors.toml"), "w") as f:
        f.write("\n".join(toml_lines) + "\n")

    # YAML
    yaml_lines = ['colors:']
    for name, val in BRAND_COLORS.items():
        yaml_lines.append(f'  {name}: "{val}"')
    yaml_lines.append('\ngradients:')
    for gname, gdef in GRADIENT_DEFINITIONS.items():
        yaml_lines.append(f'  {gname}:')
        yaml_lines.append(f'    type: "{gdef["type"]}"')
        yaml_lines.append('    stops:')
        for s in gdef["stops"]:
            yaml_lines.append(f'      - offset: "{s["offset"]}"')
            yaml_lines.append(f'        color: "{s["color"]}"')
    with open(os.path.join(colors_dir, "colors.yaml"), "w") as f:
        f.write("\n".join(yaml_lines) + "\n")

    logger.info("Colors: generated JSON/CSS/SCSS/QML/TOML/YAML")


# ---------------------------------------------------------------------------
# Per-scheme JSON theme files
# ---------------------------------------------------------------------------

def generate_theme_json(themes_dir: str):
    for scheme_name, scheme in THEME_SCHEMES.items():
        with open(os.path.join(themes_dir, f"{scheme_name}_theme.json"), "w") as f:
            json.dump(scheme, f, indent=2)
    logger.info(f"Themes: wrote {len(THEME_SCHEMES)} JSON theme files")


# ---------------------------------------------------------------------------
# GTK3 CSS
# ---------------------------------------------------------------------------

def generate_gtk3_css(gtk_dir: str):
    dark = THEME_SCHEMES["dark"]
    css = f"""/* PyFlare GTK3 Theme — Dark */
/* Auto-generated by PyFlare Branding Generator */

@define-color pf_background  {dark["background"]};
@define-color pf_surface      {dark["surface"]};
@define-color pf_primary      {dark["primary"]};
@define-color pf_accent       {dark["accent"]};
@define-color pf_text         {dark["text"]};
@define-color pf_text_sec     {dark["text_secondary"]};
@define-color pf_border       {dark["border"]};
@define-color pf_hover        {dark["hover"]};
@define-color pf_error        {dark["error"]};
@define-color pf_success      {dark["success"]};
@define-color pf_warning      {dark["warning"]};

* {{
  -gtk-icon-style: symbolic;
  font-family: "Inter", "Cantarell", sans-serif;
  font-size: 15px;
  color: @pf_text;
}}

window, .background {{
  background-color: @pf_background;
  color: @pf_text;
}}

headerbar {{
  background-color: @pf_surface;
  border-bottom: 1px solid @pf_border;
  box-shadow: 0 1px 4px rgba(0,0,0,0.5);
}}

button {{
  background-color: @pf_surface;
  border: 1px solid @pf_border;
  border-radius: 8px;
  padding: 6px 14px;
  color: @pf_text;
  transition: all 200ms ease;
}}

button:hover {{
  background-color: @pf_hover;
  border-color: @pf_primary;
}}

button:active {{
  background-color: @pf_primary;
  color: white;
}}

button.suggested-action {{
  background: linear-gradient(135deg, {dark["primary"]}, {dark["accent"]});
  color: white;
  border: none;
}}

button.destructive-action {{
  background-color: @pf_error;
  color: white;
  border: none;
}}

entry {{
  background-color: @pf_surface;
  border: 1px solid @pf_border;
  border-radius: 8px;
  padding: 8px 12px;
  color: @pf_text;
}}

entry:focus {{
  border-color: @pf_primary;
  box-shadow: 0 0 0 2px alpha(@pf_primary, 0.3);
}}

.sidebar {{
  background-color: @pf_surface;
  border-right: 1px solid @pf_border;
}}

row:selected {{
  background-color: alpha(@pf_primary, 0.2);
  color: @pf_text;
}}

progressbar > trough {{
  background-color: @pf_border;
  border-radius: 9999px;
}}

progressbar > trough > progress {{
  background: linear-gradient(90deg, {dark["primary"]}, {dark["accent"]});
  border-radius: 9999px;
}}

scrollbar slider {{
  background-color: @pf_border;
  border-radius: 9999px;
  min-width: 8px;
  min-height: 8px;
}}

scrollbar slider:hover {{
  background-color: @pf_primary;
}}

tooltip {{
  background-color: @pf_surface;
  border: 1px solid @pf_border;
  border-radius: 8px;
  color: @pf_text;
}}

checkbutton check, radiobutton radio {{
  background-color: @pf_surface;
  border: 2px solid @pf_border;
}}

checkbutton check:checked, radiobutton radio:checked {{
  background-color: @pf_primary;
  border-color: @pf_primary;
}}
"""
    with open(os.path.join(gtk_dir, "gtk.css"), "w") as f:
        f.write(css)


# ---------------------------------------------------------------------------
# GTK4 CSS
# ---------------------------------------------------------------------------

def generate_gtk4_css(gtk_dir: str):
    dark = THEME_SCHEMES["dark"]
    css = f"""/* PyFlare GTK4 Theme */
/* Auto-generated by PyFlare Branding Generator */

window {{
  background-color: {dark["background"]};
  color: {dark["text"]};
  font-family: "Inter", system-ui, sans-serif;
  font-size: 15px;
}}

.titlebar {{
  background-color: {dark["surface"]};
  border-bottom: 1px solid {dark["border"]};
}}

button {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 6px 16px;
  color: {dark["text"]};
  transition: background 200ms, border-color 200ms;
}}

button:hover {{
  background-color: {dark["hover"]};
  border-color: {dark["primary"]};
}}

button.suggested-action {{
  background: linear-gradient(135deg, {dark["primary"]}, {dark["accent"]});
  border: none;
  color: white;
}}

entry {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 8px 12px;
  color: {dark["text"]};
}}

entry:focus-within {{
  border-color: {dark["primary"]};
  outline: 2px solid alpha({dark["primary"]}, 0.3);
}}

listview row:selected {{
  background: alpha({dark["primary"]}, 0.2);
}}

progressbar progress {{
  background: linear-gradient(90deg, {dark["primary"]}, {dark["accent"]});
  border-radius: 9999px;
}}
"""
    with open(os.path.join(gtk_dir, "gtk4.css"), "w") as f:
        f.write(css)


# ---------------------------------------------------------------------------
# Qt stylesheet (.qss)
# ---------------------------------------------------------------------------

def generate_qt_stylesheet(qt_dir: str):
    dark = THEME_SCHEMES["dark"]
    qss = f"""/* PyFlare Qt/PySide6 Stylesheet */
/* Auto-generated by PyFlare Branding Generator */

QWidget {{
  background-color: {dark["background"]};
  color: {dark["text"]};
  font-family: "Inter", sans-serif;
  font-size: 15px;
}}

QMainWindow, QDialog {{
  background-color: {dark["background"]};
}}

QFrame {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
}}

QPushButton {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 6px 16px;
  color: {dark["text"]};
}}

QPushButton:hover {{
  background-color: {dark["hover"]};
  border-color: {dark["primary"]};
}}

QPushButton:pressed {{
  background-color: {dark["pressed"]};
}}

QPushButton#primaryButton {{
  background-color: {dark["primary"]};
  border: none;
  color: white;
  font-weight: 600;
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 6px 10px;
  color: {dark["text"]};
  selection-background-color: {dark["primary"]};
}}

QLineEdit:focus {{
  border-color: {dark["primary"]};
}}

QListWidget, QTreeWidget, QTableWidget {{
  background-color: {dark["surface"]};
  alternate-background-color: {dark["hover"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
}}

QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
  background-color: {dark["selected"]};
  color: {dark["text"]};
}}

QScrollBar:vertical {{
  width: 8px;
  background: {dark["surface"]};
  border-radius: 4px;
}}

QScrollBar::handle:vertical {{
  background: {dark["border"]};
  border-radius: 4px;
  min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
  background: {dark["primary"]};
}}

QProgressBar {{
  background-color: {dark["border"]};
  border-radius: 9999px;
  height: 8px;
  text-align: center;
}}

QProgressBar::chunk {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 {dark["primary"]}, stop:1 {dark["accent"]});
  border-radius: 9999px;
}}

QComboBox {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 6px 10px;
  color: {dark["text"]};
}}

QComboBox::drop-down {{
  border: none;
}}

QMenuBar {{
  background-color: {dark["surface"]};
  color: {dark["text"]};
  border-bottom: 1px solid {dark["border"]};
}}

QMenu {{
  background-color: {dark["surface"]};
  border: 1px solid {dark["border"]};
  border-radius: 8px;
  padding: 4px;
}}

QMenu::item:selected {{
  background-color: {dark["hover"]};
  border-radius: 6px;
}}

QToolTip {{
  background-color: {dark["surface"]};
  color: {dark["text"]};
  border: 1px solid {dark["border"]};
  border-radius: 6px;
  padding: 4px 8px;
}}

QTabBar::tab {{
  background-color: {dark["surface"]};
  color: {dark["text_secondary"]};
  padding: 8px 16px;
  border-bottom: 2px solid transparent;
}}

QTabBar::tab:selected {{
  color: {dark["primary"]};
  border-bottom-color: {dark["primary"]};
}}

QStatusBar {{
  background-color: {dark["surface"]};
  color: {dark["text_secondary"]};
  border-top: 1px solid {dark["border"]};
}}
"""
    with open(os.path.join(qt_dir, "pyflare.qss"), "w") as f:
        f.write(qss)


# ---------------------------------------------------------------------------
# KDE color scheme (.colors INI format)
# ---------------------------------------------------------------------------

def generate_kde_colors(kde_dir: str):
    dark = THEME_SCHEMES["dark"]

    def hex_to_kde(h):
        """Convert #RRGGBB to R,G,B"""
        h = h.lstrip("#")
        return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"

    bg  = dark["background"]
    sur = dark["surface"]
    pri = dark["primary"]
    acc = dark["accent"]
    txt = dark["text"]
    txt2= dark["text_secondary"]
    err = dark["error"]
    ok  = dark["success"]

    kde_cfg = f"""[ColorScheme]
Name=PyFlare Dark
ColorSchemeVersion=2

[Colors:Button]
BackgroundAlternate={hex_to_kde(sur)}
BackgroundNormal={hex_to_kde(sur)}
DecorationFocus={hex_to_kde(pri)}
DecorationHover={hex_to_kde(pri)}
ForegroundActive={hex_to_kde(acc)}
ForegroundInactive={hex_to_kde(txt2)}
ForegroundLink={hex_to_kde(pri)}
ForegroundNegative={hex_to_kde(err)}
ForegroundNeutral={hex_to_kde(dark["warning"])}
ForegroundNormal={hex_to_kde(txt)}
ForegroundPositive={hex_to_kde(ok)}
ForegroundVisited={hex_to_kde(acc)}

[Colors:Selection]
BackgroundAlternate={hex_to_kde(pri)}
BackgroundNormal={hex_to_kde(pri)}
DecorationFocus={hex_to_kde(pri)}
DecorationHover={hex_to_kde(acc)}
ForegroundActive={hex_to_kde(txt)}
ForegroundInactive={hex_to_kde(txt2)}
ForegroundLink={hex_to_kde(acc)}
ForegroundNegative={hex_to_kde(err)}
ForegroundNeutral=255,200,0
ForegroundNormal={hex_to_kde(txt)}
ForegroundPositive={hex_to_kde(ok)}
ForegroundVisited={hex_to_kde(acc)}

[Colors:View]
BackgroundAlternate={hex_to_kde(sur)}
BackgroundNormal={hex_to_kde(bg)}
DecorationFocus={hex_to_kde(pri)}
DecorationHover={hex_to_kde(pri)}
ForegroundActive={hex_to_kde(acc)}
ForegroundInactive={hex_to_kde(txt2)}
ForegroundLink={hex_to_kde(pri)}
ForegroundNegative={hex_to_kde(err)}
ForegroundNeutral={hex_to_kde(dark["warning"])}
ForegroundNormal={hex_to_kde(txt)}
ForegroundPositive={hex_to_kde(ok)}
ForegroundVisited={hex_to_kde(acc)}

[Colors:Window]
BackgroundAlternate={hex_to_kde(sur)}
BackgroundNormal={hex_to_kde(bg)}
DecorationFocus={hex_to_kde(pri)}
DecorationHover={hex_to_kde(pri)}
ForegroundActive={hex_to_kde(acc)}
ForegroundInactive={hex_to_kde(txt2)}
ForegroundLink={hex_to_kde(pri)}
ForegroundNegative={hex_to_kde(err)}
ForegroundNeutral={hex_to_kde(dark["warning"])}
ForegroundNormal={hex_to_kde(txt)}
ForegroundPositive={hex_to_kde(ok)}
ForegroundVisited={hex_to_kde(acc)}

[General]
ColorScheme=PyFlare Dark
Name=PyFlare Dark
shadeSortColumn=true

[KDE]
contrast=6
"""
    with open(os.path.join(kde_dir, "PyFlare.colors"), "w") as f:
        f.write(kde_cfg)


# ---------------------------------------------------------------------------
# Terminal color schemes
# ---------------------------------------------------------------------------

def generate_terminal_themes(term_dir: str):
    dark = THEME_SCHEMES["dark"]

    # Alacritty TOML
    alacritty = f"""# PyFlare Alacritty Color Scheme
# Auto-generated by PyFlare Branding Generator

[colors.primary]
background = "{dark["background"]}"
foreground = "{dark["text"]}"
dim_foreground = "{dark["text_secondary"]}"

[colors.normal]
black   = "#1E293B"
red     = "{dark["error"]}"
green   = "{dark["success"]}"
yellow  = "{dark["warning"]}"
blue    = "{dark["primary"]}"
magenta = "{BRAND_COLORS["violet"]}"
cyan    = "{dark["accent"]}"
white   = "{dark["text"]}"

[colors.bright]
black   = "#334155"
red     = "#F87171"
green   = "#34D399"
yellow  = "#FCD34D"
blue    = "#60A5FA"
magenta = "#A78BFA"
cyan    = "#38BDF8"
white   = "#F8FAFC"

[colors.cursor]
cursor = "{dark["primary"]}"
text   = "{dark["background"]}"

[colors.selection]
background = "{dark["selected"]}"
text       = "{dark["text"]}"
"""
    with open(os.path.join(term_dir, "alacritty.toml"), "w") as f:
        f.write(alacritty)

    # Windows Terminal JSON
    wt_scheme = {
        "name": "PyFlare Dark",
        "background": dark["background"],
        "foreground": dark["text"],
        "black":   "#1E293B",
        "red":     dark["error"],
        "green":   dark["success"],
        "yellow":  dark["warning"],
        "blue":    dark["primary"],
        "purple":  BRAND_COLORS["violet"],
        "cyan":    dark["accent"],
        "white":   dark["text"],
        "brightBlack":   "#334155",
        "brightRed":     "#F87171",
        "brightGreen":   "#34D399",
        "brightYellow":  "#FCD34D",
        "brightBlue":    "#60A5FA",
        "brightPurple":  "#A78BFA",
        "brightCyan":    "#38BDF8",
        "brightWhite":   "#F8FAFC",
        "cursorColor":   dark["primary"],
        "selectionBackground": dark["selected"],
    }
    with open(os.path.join(term_dir, "windows_terminal.json"), "w") as f:
        json.dump({"schemes": [wt_scheme]}, f, indent=2)

    # GNOME Terminal dconf snippet
    dconf = f"""# PyFlare GNOME Terminal profile (dconf dump excerpt)
# Load with: dconf load /org/gnome/terminal/legacy/profiles:/:pyflare/ < gnome.dconf

[/]
background-color='{dark["background"]}'
foreground-color='{dark["text"]}'
bold-color='{dark["text"]}'
cursor-background-color='{dark["primary"]}'
cursor-foreground-color='{dark["background"]}'
palette=['{dark["background"]}', '{dark["error"]}', '{dark["success"]}', '{dark["warning"]}', '{dark["primary"]}', '{BRAND_COLORS["violet"]}', '{dark["accent"]}', '{dark["text"]}', '#334155', '#F87171', '#34D399', '#FCD34D', '#60A5FA', '#A78BFA', '#38BDF8', '#F8FAFC']
use-theme-colors=false
use-theme-background=false
visible-name='PyFlare'
"""
    with open(os.path.join(term_dir, "gnome.dconf"), "w") as f:
        f.write(dconf)


# ---------------------------------------------------------------------------
# VS Code theme
# ---------------------------------------------------------------------------

def generate_vscode_theme(vscode_dir: str):
    dark = THEME_SCHEMES["dark"]
    theme = {
        "name":  "PyFlare Dark",
        "$schema": "vscode://schemas/color-theme",
        "type":  "dark",
        "colors": {
            "editor.background":              dark["background"],
            "editor.foreground":              dark["text"],
            "editorLineNumber.foreground":    dark["text_secondary"],
            "editorLineNumber.activeForeground": dark["text"],
            "editor.selectionBackground":     dark["selected"],
            "editor.lineHighlightBackground": dark["surface"],
            "editorCursor.foreground":        dark["primary"],
            "editorWhitespace.foreground":    dark["border"],
            "sideBar.background":             dark["surface"],
            "sideBar.foreground":             dark["text"],
            "sideBarSectionHeader.background": dark["hover"],
            "activityBar.background":         dark["background"],
            "activityBar.foreground":         dark["text"],
            "activityBar.inactiveForeground": dark["text_secondary"],
            "activityBarBadge.background":    dark["primary"],
            "activityBarBadge.foreground":    "#FFFFFF",
            "statusBar.background":           dark["primary"],
            "statusBar.foreground":           "#FFFFFF",
            "titleBar.activeBackground":      dark["surface"],
            "titleBar.activeForeground":      dark["text"],
            "tab.activeBackground":           dark["background"],
            "tab.inactiveBackground":         dark["surface"],
            "tab.activeBorder":               dark["primary"],
            "panel.background":               dark["surface"],
            "panel.border":                   dark["border"],
            "panelTitle.activeForeground":    dark["primary"],
            "terminal.background":            dark["background"],
            "terminal.foreground":            dark["text"],
            "terminal.ansiBlue":              dark["primary"],
            "terminal.ansiCyan":              dark["accent"],
            "terminal.ansiGreen":             dark["success"],
            "terminal.ansiRed":               dark["error"],
            "terminal.ansiYellow":            dark["warning"],
            "terminal.ansiMagenta":           BRAND_COLORS["violet"],
            "list.activeSelectionBackground": dark["selected"],
            "list.hoverBackground":           dark["hover"],
            "list.focusBackground":           dark["hover"],
            "input.background":               dark["surface"],
            "input.border":                   dark["border"],
            "input.foreground":               dark["text"],
            "focusBorder":                    dark["primary"],
            "button.background":              dark["primary"],
            "button.foreground":              "#FFFFFF",
            "badge.background":               dark["primary"],
            "badge.foreground":               "#FFFFFF",
            "progressBar.background":         dark["primary"],
            "notifications.background":       dark["surface"],
            "notifications.border":           dark["border"],
            "dropdown.background":            dark["surface"],
            "dropdown.border":                dark["border"],
            "scrollbar.shadow":               "transparent",
            "scrollbarSlider.background":     dark["border"],
            "scrollbarSlider.hoverBackground": dark["primary"],
            "editorWidget.background":        dark["surface"],
            "editorWidget.border":            dark["border"],
        },
        "tokenColors": [
            {"scope": "comment",           "settings": {"foreground": dark["text_secondary"], "fontStyle": "italic"}},
            {"scope": "string",            "settings": {"foreground": "#34D399"}},
            {"scope": "constant.numeric",  "settings": {"foreground": "#FB923C"}},
            {"scope": "constant.language", "settings": {"foreground": BRAND_COLORS["violet"]}},
            {"scope": "keyword",           "settings": {"foreground": dark["accent"]}},
            {"scope": "keyword.control",   "settings": {"foreground": dark["accent"], "fontStyle": "bold"}},
            {"scope": "storage.type",      "settings": {"foreground": dark["primary"]}},
            {"scope": "entity.name.type",  "settings": {"foreground": "#FCD34D"}},
            {"scope": "entity.name.function", "settings": {"foreground": BRAND_COLORS["violet"]}},
            {"scope": "variable",          "settings": {"foreground": dark["text"]}},
            {"scope": "variable.parameter","settings": {"foreground": "#FCD34D"}},
            {"scope": "support.function",  "settings": {"foreground": dark["primary"]}},
            {"scope": "support.class",     "settings": {"foreground": "#FCD34D"}},
            {"scope": "punctuation",       "settings": {"foreground": dark["text_secondary"]}},
            {"scope": "operator",          "settings": {"foreground": dark["accent"]}},
            {"scope": "tag",               "settings": {"foreground": dark["primary"]}},
            {"scope": "attribute.name",    "settings": {"foreground": dark["accent"]}},
            {"scope": "attribute.value",   "settings": {"foreground": "#34D399"}},
            {"scope": "invalid",           "settings": {"foreground": dark["error"], "fontStyle": "underline"}},
        ],
        "semanticHighlighting": True,
    }
    with open(os.path.join(vscode_dir, "PyFlare-color-theme.json"), "w") as f:
        json.dump(theme, f, indent=2)


# ---------------------------------------------------------------------------
# GNOME accent color script
# ---------------------------------------------------------------------------

def generate_gnome_accent(themes_dir: str):
    dark = THEME_SCHEMES["dark"]
    script = f"""#!/bin/sh
# PyFlare GNOME Accent Color Configuration
# Run this script to apply PyFlare colours to GNOME

# Set accent colour (GNOME 44+)
gsettings set org.gnome.desktop.interface accent-color 'blue'

# Set GTK theme (if installed)
gsettings set org.gnome.desktop.interface gtk-theme 'PyFlare-Dark'
gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark'
gsettings set org.gnome.desktop.interface font-name 'Inter 11'
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 11'
gsettings set org.gnome.desktop.interface document-font-name 'Inter 11'

echo "PyFlare GNOME accent applied."
"""
    with open(os.path.join(themes_dir, "apply_gnome_accent.sh"), "w") as f:
        f.write(script)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_all_themes(target_root: str) -> None:
    generate_color_files(target_root)

    themes_dir  = ensure_dir(os.path.join(target_root, "themes"))
    gtk_dir     = ensure_dir(os.path.join(themes_dir,  "gtk"))
    qt_dir      = ensure_dir(os.path.join(themes_dir,  "qt"))
    kde_dir     = ensure_dir(os.path.join(themes_dir,  "kde"))
    term_dir    = ensure_dir(os.path.join(themes_dir,  "terminal"))
    vscode_dir  = ensure_dir(os.path.join(themes_dir,  "vscode"))

    generate_theme_json(themes_dir)
    generate_gtk3_css(gtk_dir)
    generate_gtk4_css(gtk_dir)
    generate_qt_stylesheet(qt_dir)
    generate_kde_colors(kde_dir)
    generate_terminal_themes(term_dir)
    generate_vscode_theme(vscode_dir)
    generate_gnome_accent(themes_dir)

    logger.info(
        "Themes: generated GTK3/GTK4, Qt QSS, KDE .colors, "
        "Alacritty/WT/GNOME terminal, VS Code theme, GNOME accent script"
    )
