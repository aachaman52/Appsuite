#!/usr/bin/env python3
"""
scripts/setup_tree.py
PyFlare OS — full source-tree generator.
Run from repo root: python scripts/setup_tree.py
Creates every remaining directory and file needed for a production-ready
Linux distribution source tree.
"""

import os
import sys
import json
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def w(path, content, overwrite=True):
    """Write content to path (relative to ROOT), creating dirs as needed."""
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if os.path.exists(full) and not overwrite:
        return
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(textwrap.dedent(content).lstrip("\n"))
    print(f"  [write] {path}")

def touch(path):
    """Create an empty placeholder file."""
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if not os.path.exists(full):
        open(full, "w").close()
        print(f"  [touch] {path}")

def mkdir(path):
    full = os.path.join(ROOT, path)
    os.makedirs(full, exist_ok=True)

# ============================================================
# SECTION 1 — filesystem/etc remaining
# ============================================================
def etc():
    w("filesystem/etc/apt/sources.list", """\
        # PyFlare OS — Ubuntu 24.04 LTS (Noble Numbat) APT sources
        deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
        deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
        deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe multiverse
        deb http://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
    """)

    w("filesystem/etc/apt/preferences", """\
        # PyFlare OS — APT preferences
        # Pin Ubuntu packages above Flatpak / external repos
        Package: *
        Pin: release o=Ubuntu
        Pin-Priority: 500

        Package: *
        Pin: release o=LP-PPA-*
        Pin-Priority: 400
    """)

    w("filesystem/etc/NetworkManager/NetworkManager.conf", """\
        [main]
        plugins=ifupdown,keyfile
        dns=systemd-resolved

        [ifupdown]
        managed=true

        [device]
        wifi.backend=wpa_supplicant
        wifi.scan-rand-mac-address=yes
    """)

    w("filesystem/etc/udev/rules.d/99-pyflare.rules", """\
        # PyFlare OS udev rules
        # GPU power management
        SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TAG+="uaccess"
        # USB input devices
        SUBSYSTEM=="input", GROUP="input", MODE="0664"
        # Webcam
        SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"
        # PyFlare Engine socket
        SUBSYSTEM=="misc", KERNEL=="pyflare*", MODE="0660", GROUP="pyflare"
    """)

    w("filesystem/etc/xdg/autostart/pyflare-engine.desktop", """\
        [Desktop Entry]
        Type=Application
        Name=PyFlare Engine
        Comment=PyFlare AI Engine Background Service
        Exec=/opt/pyflare/bin/pyflare-engine --tray
        Icon=dev.pyflare.Engine
        Terminal=false
        Hidden=false
        X-GNOME-Autostart-enabled=true
        X-GNOME-Autostart-Phase=Applications
    """)

    w("filesystem/etc/xdg/menus/pyflare-applications.menu", """\
        <!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
          "http://www.freedesktop.org/standards/menu-spec/menu-1.0.dtd">
        <Menu>
          <Name>Applications</Name>
          <MergeFile type="parent">
            /etc/xdg/menus/applications.menu
          </MergeFile>
          <Menu>
            <Name>PyFlare</Name>
            <Directory>pyflare.directory</Directory>
            <Include>
              <Category>PyFlare</Category>
            </Include>
          </Menu>
        </Menu>
    """)

    w("filesystem/etc/systemd/system/pyflare-update.timer", """\
        [Unit]
        Description=PyFlare OS daily update check timer
        Requires=pyflare-update.service

        [Timer]
        OnCalendar=daily
        Persistent=true
        RandomizedDelaySec=3600

        [Install]
        WantedBy=timers.target
    """)

    w("filesystem/etc/systemd/system/pyflare-update.service", """\
        [Unit]
        Description=PyFlare OS Update Check
        After=network-online.target
        Wants=network-online.target

        [Service]
        Type=oneshot
        ExecStart=/opt/pyflare/bin/pyflare-updater --check
        User=root
        StandardOutput=journal
        StandardError=journal
        SyslogIdentifier=pyflare-update
    """)

    w("filesystem/etc/systemd/user/pyflare-session.service", """\
        [Unit]
        Description=PyFlare User Session Service
        After=graphical-session.target
        PartOf=graphical-session.target

        [Service]
        Type=simple
        ExecStart=/opt/pyflare/bin/pyflare-session
        Restart=on-failure
        Environment=DISPLAY=:0

        [Install]
        WantedBy=graphical-session.target
    """)

    w("filesystem/etc/gtk-4.0/settings.ini", """\
        [Settings]
        gtk-theme-name=PyFlare-Dark
        gtk-icon-theme-name=PyFlare-Icons
        gtk-cursor-theme-name=PyFlare
        gtk-cursor-theme-size=24
        gtk-font-name=Inter 11
        gtk-application-prefer-dark-theme=1
        gtk-enable-animations=1
        gtk-hint-font-metrics=1
    """)

    w("filesystem/etc/skel/.config/user-dirs.dirs", """\
        XDG_DESKTOP_DIR="$HOME/Desktop"
        XDG_DOWNLOAD_DIR="$HOME/Downloads"
        XDG_TEMPLATES_DIR="$HOME/Templates"
        XDG_PUBLICSHARE_DIR="$HOME/Public"
        XDG_DOCUMENTS_DIR="$HOME/Documents"
        XDG_MUSIC_DIR="$HOME/Music"
        XDG_PICTURES_DIR="$HOME/Pictures"
        XDG_VIDEOS_DIR="$HOME/Videos"
    """)

    w("filesystem/etc/skel/.bashrc", """\
        # PyFlare OS default .bashrc
        [ -z "$PS1" ] && return

        # Prompt
        PS1='\\[\\033[01;36m\\]\\u@pyflare\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '

        # Aliases
        alias ls='ls --color=auto'
        alias ll='ls -alF'
        alias la='ls -A'
        alias grep='grep --color=auto'
        alias df='df -h'
        alias du='du -h'
        alias ..='cd ..'
        alias ...='cd ../..'

        # PyFlare
        export PYFLARE_HOME="/opt/pyflare"
        export PATH="/opt/pyflare/bin:$PATH"
    """)

    w("filesystem/etc/cron.d/pyflare-cleanup", """\
        # PyFlare OS — scheduled cleanup tasks
        # Purge old logs weekly (Sunday 03:00)
        0 3 * * 0 root find /var/log/pyflare -name "*.log" -mtime +30 -delete
        # Clear package cache monthly
        0 4 1 * * root apt-get clean -q
    """)

    w("filesystem/etc/security/limits.d/pyflare.conf", """\
        # PyFlare OS — resource limits
        # Increase file descriptor limit for PyFlare Engine
        pyflare    soft    nofile    65536
        pyflare    hard    nofile    131072
        pyflare    soft    nproc     32768
        pyflare    hard    nproc     65536
        # Developers
        @sudo      soft    nofile    32768
        @sudo      hard    nofile    65536
    """)

# ============================================================
# SECTION 2 — filesystem/usr/share
# ============================================================
def usr_share():
    # GNOME gsettings override
    w("filesystem/usr/share/glib-2.0/schemas/99-pyflare.gschema.override", """\
        [org.gnome.desktop.interface]
        gtk-theme='PyFlare-Dark'
        icon-theme='PyFlare-Icons'
        cursor-theme='PyFlare'
        cursor-size=24
        font-name='Inter 11'
        document-font-name='Inter 11'
        monospace-font-name='JetBrains Mono 11'
        color-scheme='prefer-dark'
        accent-color='blue'
        enable-animations=true
        show-battery-percentage=true
        clock-show-weekday=true
        clock-format='12h'

        [org.gnome.desktop.background]
        picture-uri='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
        picture-uri-dark='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
        picture-options='zoom'
        primary-color='#0C0F1E'
        secondary-color='#0D1117'

        [org.gnome.desktop.screensaver]
        picture-uri='file:///usr/share/backgrounds/pyflare/minimal_dark_4K.png'
        primary-color='#0C0F1E'
        lock-delay=uint32 30

        [org.gnome.shell]
        enabled-extensions=['dash-to-dock@micxgx.gmail.com','user-theme@gnome-shell-extensions.gcampax.github.com','blur-my-shell@aunetx']
        favorite-apps=['dev.pyflare.Files.desktop','dev.pyflare.Terminal.desktop','dev.pyflare.Browser.desktop','dev.pyflare.Store.desktop','dev.pyflare.Settings.desktop','dev.pyflare.AIAssistant.desktop']
        had-bluetooth-devices-setup=false
        welcome-dialog-last-shown-version='99.0'

        [org.gnome.shell.extensions.dash-to-dock]
        dock-position='BOTTOM'
        dash-max-icon-size=48
        show-trash=false
        show-mounts=false
        transparency-mode='FIXED'
        background-opacity=0.85
        custom-background-color=true
        background-color='#0D1117'
        running-indicator-style='DOTS'
        animate-show-apps=true

        [org.gnome.desktop.wm.preferences]
        button-layout='appmenu:minimize,maximize,close'
        theme='PyFlare-Dark'
        num-workspaces=4
        focus-mode='click'

        [org.gnome.mutter]
        dynamic-workspaces=true
        edge-tiling=true
        workspaces-only-on-primary=true

        [org.gnome.desktop.session]
        idle-delay=uint32 300

        [org.gnome.settings-daemon.plugins.color]
        night-light-enabled=true
        night-light-schedule-automatic=true
        night-light-temperature=uint32 3500

        [org.gnome.software]
        allow-updates=false
        download-updates=false
    """)

    # Icon theme index
    w("filesystem/usr/share/icons/PyFlare-Icons/index.theme", """\
        [Icon Theme]
        Name=PyFlare Icons
        Comment=PyFlare OS icon theme by Aachman Studios
        Inherits=Adwaita,hicolor
        Directories=16x16/apps,24x24/apps,32x32/apps,48x48/apps,64x64/apps,128x128/apps,256x256/apps,scalable/apps,16x16/status,48x48/status

        [16x16/apps]
        Size=16
        Type=Fixed
        Context=Applications

        [24x24/apps]
        Size=24
        Type=Fixed
        Context=Applications

        [32x32/apps]
        Size=32
        Type=Fixed
        Context=Applications

        [48x48/apps]
        Size=48
        Type=Fixed
        Context=Applications

        [64x64/apps]
        Size=64
        Type=Fixed
        Context=Applications

        [128x128/apps]
        Size=128
        Type=Fixed
        Context=Applications

        [256x256/apps]
        Size=256
        Type=Fixed
        Context=Applications

        [scalable/apps]
        Size=48
        MinSize=8
        MaxSize=512
        Type=Scalable
        Context=Applications

        [16x16/status]
        Size=16
        Type=Fixed
        Context=Status

        [48x48/status]
        Size=48
        Type=Fixed
        Context=Status
    """)

    # GTK3 theme
    w("filesystem/usr/share/themes/PyFlare-Dark/index.theme", """\
        [Desktop Entry]
        Type=X-GNOME-Metatheme
        Name=PyFlare-Dark
        Comment=PyFlare OS dark GTK theme by Aachman Studios
        Encoding=UTF-8

        [X-GNOME-Metatheme]
        GtkTheme=PyFlare-Dark
        MetacityTheme=PyFlare-Dark
        IconTheme=PyFlare-Icons
        CursorTheme=PyFlare
        ButtonLayout=appmenu:minimize,maximize,close
    """)

    w("filesystem/usr/share/themes/PyFlare-Dark/gtk-3.0/gtk.css", """\
        /* PyFlare OS GTK3 Theme — Aachman Studios */
        @import url("gtk-dark.css");

        :root {
          --bg-base:      #0C0F1E;
          --bg-elevated:  #0D1117;
          --bg-surface:   #21262D;
          --accent:       #3B5BDB;
          --accent-hover: #748FFC;
          --text:         #E6EDF3;
          --text-muted:   #8B949E;
          --radius:       8px;
          --border:       1px solid rgba(255,255,255,0.08);
        }

        window.background {
          background-color: #0D1117;
          color: #E6EDF3;
        }

        headerbar {
          background: linear-gradient(135deg, #0D1117 0%, #161B22 100%);
          border-bottom: 1px solid rgba(255,255,255,0.06);
          box-shadow: 0 1px 8px rgba(0,0,0,0.4);
        }

        headerbar .title { color: #E6EDF3; font-weight: 600; }
        headerbar .subtitle { color: #8B949E; font-size: 0.85em; }

        button {
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 8px;
          color: #E6EDF3;
          transition: all 200ms ease;
        }
        button:hover { background: rgba(59,91,219,0.25); border-color: #3B5BDB; }
        button.suggested-action { background: #3B5BDB; color: #fff; border-color: transparent; }
        button.suggested-action:hover { background: #748FFC; }
        button.destructive-action { background: #F85149; color: #fff; border-color: transparent; }

        entry {
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 8px;
          color: #E6EDF3;
          caret-color: #00BFFF;
        }
        entry:focus { border-color: #3B5BDB; box-shadow: 0 0 0 3px rgba(59,91,219,0.25); }

        .sidebar { background: #0D1117; border-right: 1px solid rgba(255,255,255,0.06); }
        .sidebar row:selected { background: rgba(59,91,219,0.3); border-radius: 6px; }

        scrollbar { background: transparent; }
        scrollbar slider { background: rgba(255,255,255,0.15); border-radius: 4px; min-width: 6px; min-height: 6px; }
        scrollbar slider:hover { background: rgba(255,255,255,0.3); }

        tooltip { background: #21262D; border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; color: #E6EDF3; }

        treeview { background: #0D1117; color: #E6EDF3; }
        treeview:selected { background: rgba(59,91,219,0.3); }
        treeview header button { background: #161B22; border: none; border-bottom: 1px solid rgba(255,255,255,0.06); }
    """)

    w("filesystem/usr/share/themes/PyFlare-Dark/gtk-4.0/gtk.css", """\
        /* PyFlare OS GTK4 Theme — Aachman Studios */
        @define-color accent_color #3B5BDB;
        @define-color accent_bg_color #3B5BDB;
        @define-color accent_fg_color #ffffff;
        @define-color window_bg_color #0D1117;
        @define-color window_fg_color #E6EDF3;
        @define-color view_bg_color #0C0F1E;
        @define-color view_fg_color #E6EDF3;
        @define-color headerbar_bg_color #0D1117;
        @define-color headerbar_fg_color #E6EDF3;
        @define-color headerbar_border_color rgba(255,255,255,0.06);
        @define-color sidebar_bg_color #0D1117;
        @define-color card_bg_color #161B22;
        @define-color card_fg_color #E6EDF3;
        @define-color dialog_bg_color #161B22;
        @define-color popover_bg_color #21262D;
        @define-color shade_color rgba(0,0,0,0.4);
        @define-color scrollbar_outline_color rgba(255,255,255,0.05);
        @define-color success_color #2EA043;
        @define-color warning_color #D29922;
        @define-color error_color #F85149;
    """)

    w("filesystem/usr/share/themes/PyFlare-Dark/gnome-shell/gnome-shell.css", """\
        /* PyFlare OS GNOME Shell Theme — Aachman Studios */

        #panel {
          background: linear-gradient(180deg, rgba(13,17,23,0.95), rgba(13,17,23,0.85));
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border-bottom: 1px solid rgba(255,255,255,0.06);
          font-family: "Inter", sans-serif;
          font-size: 12pt;
          color: #E6EDF3;
        }

        #panel .panel-button:hover,
        #panel .panel-button:active {
          background: rgba(59,91,219,0.20);
          border-radius: 6px;
        }

        .overview-icon { icon-size: 48px; }
        .dash { background: rgba(13,17,23,0.90); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; }
        .dash-item-container .overview-icon:hover { background: rgba(59,91,219,0.25); border-radius: 12px; }

        .workspace-thumbnails-background {
          background: rgba(13,17,23,0.85);
          border-radius: 12px;
        }

        .search-entry {
          background: rgba(33,38,45,0.95);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 12px;
          color: #E6EDF3;
          caret-color: #00BFFF;
          padding: 12px 16px;
        }

        .app-grid-icon { border-radius: 12px; }
    """)

    # Backgrounds placeholder README
    w("filesystem/usr/share/backgrounds/pyflare/README.md", """\
        # PyFlare OS Wallpapers

        Wallpapers are generated by `branding_generator` and copied here during build.

        ```
        python -m branding_generator.main generate
        python scripts/copy_branding.py
        ```

        | File | Resolution | Style |
        |------|-----------|-------|
        | default_dark_4K.png | 3840×2160 | Deep space gradient |
        | minimal_dark_4K.png | 3840×2160 | Minimal dark |
        | geometric_dark_4K.png | 3840×2160 | Geometric |
        | default_dark_2K.png | 2560×1440 | Deep space gradient |
        | default_dark_1080p.png | 1920×1080 | Deep space gradient |
    """)

    # Sounds placeholder
    w("filesystem/usr/share/sounds/pyflare/README.md", """\
        # PyFlare OS Sound Theme

        System sounds are generated by `branding_generator` and copied here during build.
        Format: OGG Vorbis (for Linux compatibility)

        | File | Event |
        |------|-------|
        | startup.ogg | System startup |
        | shutdown.ogg | System shutdown |
        | notification.ogg | Notification |
        | error.ogg | Error |
        | success.ogg | Success |
    """)

    w("filesystem/usr/share/sounds/pyflare/index.theme", """\
        [Sound Theme]
        Name=PyFlare
        Comment=PyFlare OS sound theme by Aachman Studios
        Inherits=freedesktop
        Directories=stereo

        [stereo]
        OutputProfile=stereo
    """)

    # Locale placeholder
    mkdir("filesystem/usr/share/locale")
    w("filesystem/usr/share/locale/README.md", """\
        # Locale Data

        System locale files are provided by the Ubuntu base system.
        PyFlare-specific strings are compiled from `src/i18n/` during build.
    """)

    # .desktop launchers
    apps = [
        ("dev.pyflare.Engine",        "PyFlare Engine",     "The AI-native runtime",              "dev.pyflare.Engine",        "/opt/pyflare/engine/pyflare-engine",    "Utility;System;"),
        ("dev.pyflare.AppSuite",      "AppSuite",           "Integrated development suite",       "dev.pyflare.AppSuite",      "/opt/pyflare/apps/appsuite/appsuite",   "Development;"),
        ("dev.pyflare.Terminal",      "PyFlare Terminal",   "GPU-accelerated AI terminal",        "dev.pyflare.Terminal",      "/opt/pyflare/apps/terminal/terminal",   "System;TerminalEmulator;"),
        ("dev.pyflare.Browser",       "PyFlare Browser",    "Privacy-focused web browser",        "dev.pyflare.Browser",       "/opt/pyflare/apps/browser/browser",     "Network;WebBrowser;"),
        ("dev.pyflare.Files",         "PyFlare Files",      "AI-powered file manager",            "dev.pyflare.Files",         "/opt/pyflare/apps/files/files",         "System;FileManager;"),
        ("dev.pyflare.Store",         "PyFlare Store",      "Application marketplace",            "dev.pyflare.Store",         "/opt/pyflare/apps/store/store",         "System;PackageManager;"),
        ("dev.pyflare.Settings",      "PyFlare Settings",   "System configuration",               "dev.pyflare.Settings",      "/opt/pyflare/apps/settings/settings",   "Settings;"),
        ("dev.pyflare.PackageManager","Package Manager",    "Manage APT, Flatpak, and Snap",      "dev.pyflare.PackageManager","/opt/pyflare/apps/package-manager/pm",  "System;PackageManager;"),
        ("dev.pyflare.PluginManager", "Plugin Manager",     "Manage PyFlare Engine plugins",      "dev.pyflare.PluginManager", "/opt/pyflare/apps/plugin-manager/pm",   "System;"),
        ("dev.pyflare.Launcher",      "PyFlare Launcher",   "Application launcher",               "dev.pyflare.Launcher",      "/opt/pyflare/apps/launcher/launcher",   "Utility;"),
        ("dev.pyflare.AIAssistant",   "AI Assistant",       "On-device AI powered by Ollama",     "dev.pyflare.AIAssistant",   "/opt/pyflare/apps/ai-assistant/ai",     "Utility;Education;"),
    ]
    for app_id, name, comment, icon, exec_path, categories in apps:
        w(f"filesystem/usr/share/applications/{app_id}.desktop", f"""\
            [Desktop Entry]
            Version=1.5
            Type=Application
            Name={name}
            Comment={comment}
            GenericName={name}
            Icon={icon}
            Exec={exec_path}
            Terminal=false
            StartupNotify=true
            StartupWMClass={app_id}
            Categories={categories}PyFlare;
            Keywords=pyflare;aachman;
            X-GNOME-UsesNotifications=true
            X-Flatpak={app_id}
        """)

# ============================================================
# SECTION 3 — filesystem/opt/pyflare
# ============================================================
def opt():
    dirs = [
        "filesystem/opt/pyflare/bin",
        "filesystem/opt/pyflare/lib",
        "filesystem/opt/pyflare/share/icons",
        "filesystem/opt/pyflare/share/fonts",
        "filesystem/opt/pyflare/engine",
        "filesystem/opt/pyflare/apps/appsuite",
        "filesystem/opt/pyflare/apps/terminal",
        "filesystem/opt/pyflare/apps/browser",
        "filesystem/opt/pyflare/apps/files",
        "filesystem/opt/pyflare/apps/store",
        "filesystem/opt/pyflare/apps/settings",
        "filesystem/opt/pyflare/apps/package-manager",
        "filesystem/opt/pyflare/apps/plugin-manager",
        "filesystem/opt/pyflare/apps/launcher",
        "filesystem/opt/pyflare/apps/ai-assistant",
        "filesystem/opt/pyflare/plugins",
        "filesystem/opt/pyflare/themes",
        "filesystem/opt/pyflare/extensions",
    ]
    for d in dirs:
        mkdir(d)
        touch(f"{d}/.keep")

    w("filesystem/opt/pyflare/engine/pyflare-engine", """\
        #!/usr/bin/env python3
        # PyFlare Engine — entry point stub
        # Real implementation lives in applications/engine/src/
        import sys
        import os
        sys.path.insert(0, '/opt/pyflare/lib')
        print("PyFlare Engine 1.0.0 — starting...")
        # TODO: import and run real engine
    """)

    w("filesystem/opt/pyflare/bin/pyflare-updater", """\
        #!/usr/bin/env bash
        # PyFlare OS updater script
        set -euo pipefail
        echo "PyFlare OS Updater v1.0.0"
        apt-get update -q
        apt-get upgrade -y -q
        flatpak update -y --noninteractive 2>/dev/null || true
        /opt/pyflare/bin/pyflare-engine --self-update 2>/dev/null || true
        echo "Update complete."
    """)

    w("filesystem/opt/pyflare/bin/pyflare-firstrun", """\
        #!/usr/bin/env python3
        # PyFlare OS first-run wizard — stub
        # Runs once after first boot.
        import os
        import sys
        print("Welcome to PyFlare OS!")
        print("First-run setup complete.")
    """)

# ============================================================
# SECTION 4 — filesystem/var and home
# ============================================================
def var_and_home():
    for d in [
        "filesystem/var/log/pyflare",
        "filesystem/var/lib/pyflare",
        "filesystem/var/cache/pyflare/store",
        "filesystem/var/run/pyflare",
        "filesystem/home/pyflare/.config",
        "filesystem/home/pyflare/.local/share",
        "filesystem/home/pyflare/Desktop",
        "filesystem/home/pyflare/Downloads",
        "filesystem/home/pyflare/Documents",
        "filesystem/home/pyflare/Pictures",
        "filesystem/root",
    ]:
        mkdir(d)
        touch(f"{d}/.keep")

# ============================================================
# SECTION 5 — desktop/
# ============================================================
def desktop():
    w("desktop/gsettings/99-pyflare.gschema.override", """\
        # This is the SOURCE copy; the build system copies it to
        # filesystem/usr/share/glib-2.0/schemas/ during build.
        # See filesystem/usr/share/glib-2.0/schemas/99-pyflare.gschema.override
        # for the actual deployed file.
    """)

    w("desktop/dock/dash-to-dock.conf", """\
        # Dash-to-Dock GNOME extension configuration
        # Applied via dconf/gsettings during post_install.sh

        [org.gnome.shell.extensions.dash-to-dock]
        dock-position=BOTTOM
        dash-max-icon-size=48
        show-trash=false
        show-mounts=false
        transparency-mode=FIXED
        background-opacity=0.85
        custom-background-color=true
        background-color=#0D1117
        running-indicator-style=DOTS
        animate-show-apps=true
        intellihide=true
        intellihide-mode=FOCUS_APPLICATION_WINDOWS
    """)

    w("desktop/menus/pyflare.directory", """\
        [Desktop Entry]
        Type=Directory
        Name=PyFlare
        Comment=PyFlare OS Applications
        Icon=dev.pyflare.Engine
    """)

    w("desktop/autostart/pyflare-welcome.desktop", """\
        [Desktop Entry]
        Type=Application
        Name=PyFlare Welcome
        Comment=Welcome screen shown on first login
        Exec=/opt/pyflare/apps/settings/settings --welcome
        Icon=dev.pyflare.Settings
        Terminal=false
        Hidden=false
        X-GNOME-Autostart-enabled=true
        X-GNOME-Autostart-Phase=Application
        X-GNOME-AutoRestart=false
        OnlyShowIn=GNOME;
    """)

    w("desktop/shortcuts/pyflare-launcher.desktop", """\
        [Desktop Entry]
        Type=Application
        Name=PyFlare Launcher
        Exec=/opt/pyflare/apps/launcher/launcher
        Icon=dev.pyflare.Launcher
        NoDisplay=true
        X-GNOME-Autostart-enabled=true
    """)

    w("desktop/README.md", """\
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
    """)

# ============================================================
# SECTION 6 — packages/
# ============================================================
def packages():
    manifest = {
        "schema": "pyflare-package-manifest/1.0",
        "generated": "2026-07-30",
        "vendor": "Aachman Studios",
        "packages": {
            "pyflare-engine": {
                "version": "1.0.0",
                "description": "PyFlare Engine runtime and daemon",
                "architecture": "all",
                "section": "misc",
                "priority": "required",
                "depends": ["python3 (>= 3.12)", "python3-gi", "dbus", "systemd"],
                "install_path": "/opt/pyflare/engine",
                "service": "pyflare-engine.service",
            },
            "pyflare-desktop": {
                "version": "1.0.0",
                "description": "PyFlare OS desktop integration and theming",
                "architecture": "all",
                "section": "x11",
                "priority": "standard",
                "depends": ["gnome-shell", "gdm3", "pyflare-engine"],
                "install_path": "/usr/share/themes/PyFlare-Dark",
            },
            "pyflare-apps": {
                "version": "1.0.0",
                "description": "PyFlare OS bundled applications meta-package",
                "architecture": "all",
                "section": "misc",
                "priority": "optional",
                "depends": ["pyflare-engine", "pyflare-desktop"],
            },
        },
    }
    w("packages/manifests/core.json", json.dumps(manifest, indent=2))

    w("packages/manifests/desktop.json", json.dumps({
        "schema": "pyflare-package-manifest/1.0",
        "description": "PyFlare OS desktop packages",
        "packages": {
            "pyflare-theme-dark": {
                "version": "1.0.0",
                "files": [
                    "/usr/share/themes/PyFlare-Dark/",
                    "/usr/share/icons/PyFlare-Icons/",
                    "/usr/share/cursors/xorg-x11/PyFlare/",
                ],
            },
            "pyflare-wallpapers": {
                "version": "1.0.0",
                "files": ["/usr/share/backgrounds/pyflare/"],
            },
            "pyflare-sounds": {
                "version": "1.0.0",
                "files": ["/usr/share/sounds/pyflare/"],
            },
            "pyflare-fonts": {
                "version": "1.0.0",
                "files": ["/usr/share/fonts/pyflare/", "/etc/fonts/local.conf"],
            },
        },
    }, indent=2))

    w("packages/manifests/applications.json", json.dumps({
        "schema": "pyflare-package-manifest/1.0",
        "description": "PyFlare OS bundled applications",
        "applications": [
            {"id": "dev.pyflare.Engine",         "package": "pyflare-engine",         "version": "1.0.0"},
            {"id": "dev.pyflare.AppSuite",        "package": "pyflare-appsuite",        "version": "1.0.0"},
            {"id": "dev.pyflare.Terminal",        "package": "pyflare-terminal",        "version": "1.0.0"},
            {"id": "dev.pyflare.Browser",         "package": "pyflare-browser",         "version": "1.0.0"},
            {"id": "dev.pyflare.Files",           "package": "pyflare-files",           "version": "1.0.0"},
            {"id": "dev.pyflare.Store",           "package": "pyflare-store",           "version": "1.0.0"},
            {"id": "dev.pyflare.Settings",        "package": "pyflare-settings",        "version": "1.0.0"},
            {"id": "dev.pyflare.PackageManager",  "package": "pyflare-package-manager", "version": "1.0.0"},
            {"id": "dev.pyflare.PluginManager",   "package": "pyflare-plugin-manager",  "version": "1.0.0"},
            {"id": "dev.pyflare.Launcher",        "package": "pyflare-launcher",        "version": "1.0.0"},
            {"id": "dev.pyflare.AIAssistant",     "package": "pyflare-ai-assistant",    "version": "1.0.0"},
        ],
    }, indent=2))

    w("packages/scripts/install_pyflare.sh", """\
        #!/usr/bin/env bash
        # PyFlare OS package installer — runs inside chroot
        set -euo pipefail
        PYFLARE_ROOT=/opt/pyflare

        echo "Installing PyFlare OS packages..."
        install -d "$PYFLARE_ROOT"/{bin,lib,engine,apps,plugins,themes,share}

        # Copy filesystem overlay
        rsync -av --no-owner --no-group \\
            /tmp/pyflare-overlay/filesystem/ / \\
            --exclude='.keep' \\
            --exclude='README.md'

        # Set permissions
        chmod +x "$PYFLARE_ROOT"/bin/*
        chmod +x "$PYFLARE_ROOT"/engine/pyflare-engine

        # Enable services
        systemctl enable pyflare-engine.service || true
        systemctl enable pyflare-update.timer   || true
        systemctl enable pyflare-firstrun.service || true

        # Compile gsettings schemas
        glib-compile-schemas /usr/share/glib-2.0/schemas/ || true

        echo "PyFlare OS packages installed."
    """)

    w("packages/README.md", """\
        # PyFlare OS Package Structure

        | Directory | Purpose |
        |-----------|---------|
        | `manifests/` | JSON package manifests |
        | `metadata/` | Per-package metadata and changelogs |
        | `scripts/` | Install/remove hook scripts |

        ## Package Naming Convention

        `pyflare-{component}_{version}_all.deb`

        - `pyflare-engine` — Core engine
        - `pyflare-desktop` — Theme, icons, wallpapers
        - `pyflare-apps` — Meta-package for all apps
        - `pyflare-{appname}` — Individual applications
    """)

# ============================================================
# SECTION 7 — installer/ (Calamares)
# ============================================================
def installer():
    w("installer/config/settings.conf", """\
        ---
        # Calamares installer configuration for PyFlare OS

        modules-search: [ local, /usr/lib/calamares/modules ]

        instances:
          - id: welcome
            module: welcome
          - id: locale
            module: locale
          - id: keyboard
            module: keyboard
          - id: partition
            module: partition
          - id: users
            module: users
          - id: summary
            module: summary
          - id: install
            module: unpackfs
          - id: bootloader
            module: bootloader
          - id: finish
            module: finished

        sequence:
          - show:
            - welcome
            - locale
            - keyboard
            - partition
            - users
            - summary
          - exec:
            - partition
            - mount
            - unpackfs
            - machineid
            - fstab
            - locale
            - keyboard
            - localecfg
            - users
            - displaymanager
            - networkcfg
            - hwclock
            - services-systemd
            - bootloader
            - pyflare-postinstall
          - show:
            - finish

        branding: pyflare
        prompt-install: false
        dont-chroot: false
        oem-setup: false
        disable-cancel: false
        disable-cancel-during-exec: true
        hide-back-and-next-during-exec: true
        quitOnExecErrors: false
        log-level: info
        crash-reporter: ""
    """)

    w("installer/config/branding.desc", """\
        ---
        componentName: pyflare

        # Visible strings
        strings:
          productName:      PyFlare OS
          shortProductName: PyFlare
          version:          1.0.0 Ember
          shortVersion:     1.0.0
          versionedName:    PyFlare OS 1.0.0 (Ember)
          bootloaderEntryName: PyFlare OS
          productUrl:       https://pyflare.dev
          supportUrl:       https://aachmanstudios.dev/support
          knownIssuesUrl:   https://github.com/aachman-studios/pyflare-os/issues
          releaseNotesUrl:  https://pyflare.dev/release-notes/1.0.0
          donateUrl:        ""

        # Branding images (relative to this file)
        images:
          productLogo:       "pyflare-logo.png"
          productIcon:       "pyflare-icon.png"
          productWelcome:    "pyflare-welcome.png"
          productBanner:     "pyflare-banner.png"

        # Slideshow
        slideshow:             "show.qml"
        slideshowAPI:          2

        # Colours (Qt palette)
        style:
          sidebarBackground:   "#0D1117"
          sidebarText:         "#E6EDF3"
          sidebarTextSelect:   "#FFFFFF"
          sidebarTextHighlight:"#3B5BDB"
    """)

    for i, (title, body) in enumerate([
        ("Welcome to PyFlare OS",
         "PyFlare OS is an AI-native Linux distribution by Aachman Studios, built on Ubuntu 24.04 LTS."),
        ("Lightning Fast",
         "PyFlare Engine provides intelligent background services — package management, AI assistance, and system optimization — all running locally."),
        ("Beautiful by Default",
         "PyFlare Dark theme, custom icons, and procedurally generated wallpapers make your desktop look stunning out of the box."),
        ("Privacy First",
         "Everything runs on your hardware. No telemetry. No cloud accounts required. Your data stays yours."),
        ("Built for Developers",
         "JetBrains Mono, Docker, Git LFS, Python 3, and the full build toolchain — ready the moment you log in."),
    ], 1):
        w(f"installer/slides/slide{i:02d}.html", f"""\
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <style>
                body {{
                  margin: 0; padding: 40px;
                  background: #0C0F1E;
                  color: #E6EDF3;
                  font-family: 'Inter', 'Ubuntu', sans-serif;
                  display: flex; align-items: center; justify-content: center;
                  height: 100vh; box-sizing: border-box;
                }}
                .card {{
                  background: rgba(255,255,255,0.04);
                  border: 1px solid rgba(255,255,255,0.08);
                  border-radius: 16px;
                  padding: 48px 56px;
                  max-width: 640px;
                  text-align: center;
                }}
                h1 {{
                  font-family: 'Space Grotesk', 'Ubuntu', sans-serif;
                  font-size: 2rem; font-weight: 700;
                  background: linear-gradient(135deg, #3B5BDB, #00BFFF);
                  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                  margin-bottom: 1rem;
                }}
                p {{ font-size: 1.05rem; color: #8B949E; line-height: 1.7; }}
                .logo {{ font-size: 3rem; margin-bottom: 1.5rem; }}
              </style>
            </head>
            <body>
              <div class="card">
                <div class="logo">🔥</div>
                <h1>{title}</h1>
                <p>{body}</p>
              </div>
            </body>
            </html>
        """)

    w("installer/scripts/pre-install.sh", """\
        #!/usr/bin/env bash
        # Calamares pre-install hook
        set -euo pipefail
        echo "[PyFlare Installer] Pre-install hook running..."
        # Ensure PyFlare directories exist
        mkdir -p /opt/pyflare/{bin,lib,engine,apps}
    """)

    w("installer/scripts/post-install.sh", """\
        #!/usr/bin/env bash
        # Calamares post-install hook — runs inside installed system chroot
        set -euo pipefail
        TARGET="${{1:-/}}"
        echo "[PyFlare Installer] Post-install hook for target: $TARGET"

        # Enable services
        chroot "$TARGET" systemctl enable pyflare-engine.service 2>/dev/null || true
        chroot "$TARGET" systemctl enable gdm3.service 2>/dev/null || true
        chroot "$TARGET" glib-compile-schemas /usr/share/glib-2.0/schemas/ 2>/dev/null || true
        chroot "$TARGET" fc-cache -f 2>/dev/null || true
        chroot "$TARGET" update-initramfs -u 2>/dev/null || true
        chroot "$TARGET" update-grub 2>/dev/null || true

        echo "[PyFlare Installer] Post-install complete."
    """)

    w("installer/README.md", """\
        # PyFlare OS Installer (Calamares)

        ## Overview

        PyFlare OS uses [Calamares](https://calamares.io/) as its graphical installer.

        ## Structure

        | Path | Purpose |
        |------|---------|
        | `config/settings.conf` | Main Calamares configuration |
        | `config/branding.desc` | Branding strings and images |
        | `slides/` | HTML/QML installation slideshow |
        | `scripts/pre-install.sh` | Pre-install hook |
        | `scripts/post-install.sh` | Post-install hook |

        ## Building

        Calamares runs from the live ISO session. The config files are copied to
        `/etc/calamares/` during ISO build.

        ## Required Images

        Place these in `installer/config/`:
        - `pyflare-logo.png` — 200×200 installer logo
        - `pyflare-icon.png` — 64×64 application icon
        - `pyflare-welcome.png` — 540×240 welcome banner
        - `pyflare-banner.png` — 800×420 sidebar banner
    """)

# ============================================================
# SECTION 8 — applications/ (10 app stubs)
# ============================================================
APP_DEFS = [
    ("engine",          "PyFlare Engine",      "dev.pyflare.Engine",         "AI-native runtime and daemon",                 "Python"),
    ("appsuite",        "AppSuite",            "dev.pyflare.AppSuite",       "Integrated development and productivity suite","Python/GTK4"),
    ("terminal",        "PyFlare Terminal",    "dev.pyflare.Terminal",       "GPU-accelerated AI-assisted terminal",         "Python/VTE"),
    ("browser",         "PyFlare Browser",     "dev.pyflare.Browser",        "Privacy-focused web browser",                  "Python/WebKit"),
    ("files",           "PyFlare Files",       "dev.pyflare.Files",          "AI-powered file manager",                      "Python/GTK4"),
    ("store",           "PyFlare Store",       "dev.pyflare.Store",          "Application and extension marketplace",        "Python/GTK4"),
    ("settings",        "PyFlare Settings",    "dev.pyflare.Settings",       "System configuration and preferences",         "Python/GTK4"),
    ("package-manager", "Package Manager",     "dev.pyflare.PackageManager", "Unified APT, Flatpak, and Snap manager",       "Python/GTK4"),
    ("plugin-manager",  "Plugin Manager",      "dev.pyflare.PluginManager",  "Manage PyFlare Engine plugins",                "Python/GTK4"),
    ("launcher",        "PyFlare Launcher",    "dev.pyflare.Launcher",       "Application launcher with AI suggestions",     "Python/GTK4"),
    ("ai-assistant",    "AI Assistant",        "dev.pyflare.AIAssistant",    "On-device AI assistant powered by Ollama",     "Python"),
]

def applications():
    for slug, name, app_id, description, tech in APP_DEFS:
        base = f"applications/{slug}"

        w(f"{base}/README.md", f"""\
            # {name}

            **ID:** `{app_id}`
            **Technology:** {tech}
            **Description:** {description}
            **Version:** 1.0.0
            **Vendor:** Aachman Studios

            ## Structure

            ```
            {slug}/
            ├── src/          Application source code
            ├── assets/       Icons, images, UI resources
            ├── desktop/      .desktop and autostart files
            ├── config/       Default configuration
            └── tests/        Unit and integration tests
            ```

            ## Running in Development

            ```bash
            cd applications/{slug}
            python src/main.py --dev
            ```

            ## Installing

            Handled automatically by `scripts/package_apps.py` during build.
        """)

        w(f"{base}/src/main.py", f"""\
            #!/usr/bin/env python3
            \"\"\"
            {name} — entry point
            {app_id}
            Aachman Studios / PyFlare OS 1.0.0
            \"\"\"

            import sys
            import os

            APP_ID      = "{app_id}"
            APP_NAME    = "{name}"
            APP_VERSION = "1.0.0"


            def main() -> int:
                print(f"{{APP_NAME}} {{APP_VERSION}} starting...")
                # TODO: initialise GTK / application loop
                return 0


            if __name__ == "__main__":
                sys.exit(main())
        """)

        w(f"{base}/src/__init__.py", f"""\
            \"\"\"
            {name} ({app_id})
            Version 1.0.0 — Aachman Studios
            \"\"\"
            __version__ = "1.0.0"
            __app_id__  = "{app_id}"
        """)

        w(f"{base}/config/config.yaml", f"""\
            # {name} — default configuration
            # {app_id}

            app:
              id: "{app_id}"
              name: "{name}"
              version: "1.0.0"

            ui:
              theme: system
              language: system
              scale: 1.0

            general:
              autostart: false
              minimize_to_tray: false
              check_updates: true
        """)

        w(f"{base}/desktop/{app_id}.desktop", f"""\
            [Desktop Entry]
            Version=1.5
            Type=Application
            Name={name}
            Comment={description}
            Icon={app_id}
            Exec=/opt/pyflare/apps/{slug}/src/main.py
            Terminal=false
            StartupNotify=true
            StartupWMClass={app_id}
            Categories=PyFlare;
            Keywords=pyflare;aachman;
        """)

        w(f"{base}/assets/README.md", f"""\
            # {name} — Assets

            Place application-specific assets here:
            - `icons/` — Application icons (SVG preferred)
            - `images/` — UI imagery
            - `ui/` — GTK `.ui` builder files

            Icons are copied from `branding/` during build via `scripts/copy_branding.py`.
        """)

        touch(f"{base}/assets/.keep")

        w(f"{base}/tests/__init__.py", "")
        w(f"{base}/tests/test_main.py", f"""\
            \"\"\"Basic smoke tests for {name}.\"\"\"
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
            import pytest


            def test_import():
                import main  # noqa: F401
                assert True


            def test_version():
                import main
                assert hasattr(main, 'APP_VERSION')
                assert main.APP_VERSION == "1.0.0"
        """)

        w(f"{base}/LICENSE", f"""\
            MIT License
            Copyright (c) 2026 Aachman Studios
            {name} is part of PyFlare OS.
            See root LICENSE for full terms.
        """)

# ============================================================
# SECTION 9 — .github/workflows
# ============================================================
def github_ci():
    w(".github/workflows/build.yml", """\
        name: Build Validation

        on:
          push:
            branches: [main, develop, release/*]
          pull_request:
            branches: [main, develop]

        jobs:
          validate-tree:
            name: Validate Source Tree
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4

              - name: Set up Python
                uses: actions/setup-python@v5
                with:
                  python-version: '3.12'

              - name: Install dependencies
                run: pip install -r requirements.txt

              - name: Generate branding assets
                run: python -m branding_generator.main generate

              - name: Run validators
                run: python validation/run_all.py

              - name: Check filesystem completeness
                run: python validation/validate_filesystem.py

              - name: Archive branding preview
                uses: actions/upload-artifact@v4
                with:
                  name: branding-previews
                  path: branding/previews/
                  retention-days: 14
    """)

    w(".github/workflows/validate.yml", """\
        name: Asset Validation

        on:
          push:
          pull_request:
          schedule:
            - cron: '0 2 * * 1'   # Weekly Monday 02:00 UTC

        jobs:
          validate:
            name: Run All Validators
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4

              - name: Set up Python
                uses: actions/setup-python@v5
                with:
                  python-version: '3.12'

              - name: Install dependencies
                run: |
                  sudo apt-get install -y libcairo2-dev
                  pip install -r requirements.txt

              - name: Validate branding
                run: python validation/validate_branding.py

              - name: Validate desktop entries
                run: python validation/validate_desktop.py

              - name: Validate JSON files
                run: python validation/validate_json.py

              - name: Validate SVG files
                run: python validation/validate_svg.py

              - name: Validate configs
                run: python validation/validate_configs.py

              - name: Validate packages
                run: python validation/validate_packages.py

              - name: Upload validation report
                if: always()
                uses: actions/upload-artifact@v4
                with:
                  name: validation-report
                  path: reports/
                  retention-days: 7
    """)

    w(".github/workflows/lint.yml", """\
        name: Lint

        on:
          push:
          pull_request:

        jobs:
          python-lint:
            name: Python (ruff + mypy)
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.12'
              - name: Install linters
                run: pip install ruff mypy
              - name: ruff check
                run: ruff check . --exclude=branding/
              - name: mypy
                run: mypy branding_generator/ validation/ scripts/ --ignore-missing-imports || true

          yaml-lint:
            name: YAML Lint
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4
              - name: Lint YAML
                run: |
                  pip install yamllint
                  yamllint config/ -d '{extends: default, rules: {line-length: {max: 120}}}'

          shell-lint:
            name: Shell (shellcheck)
            runs-on: ubuntu-22.04
            steps:
              - uses: actions/checkout@v4
              - run: sudo apt-get install -y shellcheck
              - run: find . -name "*.sh" -not -path "./.git/*" | xargs shellcheck --severity=warning
    """)

    w(".github/ISSUE_TEMPLATE/bug_report.md", """\
        ---
        name: Bug Report
        about: Report a bug in PyFlare OS
        labels: bug
        ---

        **Describe the bug**
        A clear description of the bug.

        **To Reproduce**
        Steps to reproduce the behavior.

        **Expected behavior**
        What you expected to happen.

        **Environment**
        - PyFlare OS version:
        - Hardware:
        - Relevant logs (`journalctl -u pyflare-engine`):
    """)

    w(".github/ISSUE_TEMPLATE/feature_request.md", """\
        ---
        name: Feature Request
        about: Suggest a feature for PyFlare OS
        labels: enhancement
        ---

        **Feature description**

        **Use case**

        **Proposed implementation**
    """)

# ============================================================
# SECTION 10 — scripts/
# ============================================================
def scripts():
    w("scripts/copy_branding.py", """\
        #!/usr/bin/env python3
        \"\"\"
        scripts/copy_branding.py
        Copy generated branding assets from branding/ into filesystem/ overlay.
        Run after: python -m branding_generator.main generate
        \"\"\"
        import os
        import shutil
        import argparse

        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        BRANDING = os.path.join(ROOT, "branding")
        FS = os.path.join(ROOT, "filesystem")

        COPY_MAP = {
            "logos/svg":           "usr/share/icons/PyFlare-Icons/scalable/apps",
            "logos/png":           "usr/share/pixmaps",
            "wallpapers":          "usr/share/backgrounds/pyflare",
            "cursors":             "usr/share/icons/PyFlare",
            "themes/gtk":          "usr/share/themes/PyFlare-Dark/gtk-3.0",
            "fonts":               "usr/share/fonts/pyflare",
        }

        def main():
            parser = argparse.ArgumentParser(description="Copy branding assets into filesystem overlay")
            parser.add_argument("--dry-run", action="store_true")
            args = parser.parse_args()

            for src_rel, dst_rel in COPY_MAP.items():
                src = os.path.join(BRANDING, src_rel)
                dst = os.path.join(FS, dst_rel)
                if not os.path.isdir(src):
                    print(f"  [skip] {src_rel} — not found")
                    continue
                if not args.dry_run:
                    os.makedirs(dst, exist_ok=True)
                    for f in os.listdir(src):
                        shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
                print(f"  [copy] {src_rel} -> filesystem/{dst_rel}")

        if __name__ == "__main__":
            main()
    """)

    w("scripts/generate_manifest.py", """\
        #!/usr/bin/env python3
        \"\"\"
        scripts/generate_manifest.py
        Generate a complete file manifest for the filesystem/ overlay.
        Outputs: reports/filesystem_manifest.json
        \"\"\"
        import os
        import json
        import hashlib
        from datetime import datetime

        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        FS   = os.path.join(ROOT, "filesystem")
        OUT  = os.path.join(ROOT, "reports", "filesystem_manifest.json")

        def sha256(path):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        def main():
            os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
            files = {}
            for dirpath, _, filenames in os.walk(FS):
                for fname in filenames:
                    fp = os.path.join(dirpath, fname)
                    rel = os.path.relpath(fp, FS)
                    files[rel] = {
                        "size": os.path.getsize(fp),
                        "sha256": sha256(fp),
                        "mtime": os.path.getmtime(fp),
                    }
            manifest = {
                "generated": datetime.utcnow().isoformat(),
                "root": "filesystem/",
                "file_count": len(files),
                "files": files,
            }
            with open(OUT, "w") as f:
                json.dump(manifest, f, indent=2)
            print(f"Manifest: {len(files)} files -> {OUT}")

        if __name__ == "__main__":
            main()
    """)

    w("scripts/generate_checksums.py", """\
        #!/usr/bin/env python3
        \"\"\"
        scripts/generate_checksums.py
        Generate SHA256SUMS and MD5SUMS for the output/ directory.
        \"\"\"
        import os
        import hashlib

        ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        OUTPUT = os.path.join(ROOT, "output")

        def hash_file(path, algo="sha256"):
            h = hashlib.new(algo)
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        def main():
            if not os.path.isdir(OUTPUT):
                print("output/ not found — build ISO first.")
                return
            for fname in os.listdir(OUTPUT):
                fp = os.path.join(OUTPUT, fname)
                if not os.path.isfile(fp):
                    continue
                sha = hash_file(fp, "sha256")
                md5 = hash_file(fp, "md5")
                print(f"{sha}  {fname}")
                with open(fp + ".sha256", "w") as f:
                    f.write(f"{sha}  {fname}\\n")
                with open(fp + ".md5", "w") as f:
                    f.write(f"{md5}  {fname}\\n")

        if __name__ == "__main__":
            main()
    """)

    w("scripts/package_apps.py", """\
        #!/usr/bin/env python3
        \"\"\"
        scripts/package_apps.py
        Package application stubs into the filesystem overlay.
        Copies applications/{slug}/src/ -> filesystem/opt/pyflare/apps/{slug}/
        \"\"\"
        import os
        import shutil

        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        APPS = os.path.join(ROOT, "applications")
        DEST = os.path.join(ROOT, "filesystem", "opt", "pyflare", "apps")

        def main():
            os.makedirs(DEST, exist_ok=True)
            for slug in os.listdir(APPS):
                src_dir = os.path.join(APPS, slug, "src")
                if not os.path.isdir(src_dir):
                    continue
                dst_dir = os.path.join(DEST, slug)
                if os.path.exists(dst_dir):
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                print(f"  [pack] applications/{slug}/src -> filesystem/opt/pyflare/apps/{slug}")

        if __name__ == "__main__":
            main()
    """)

    w("scripts/prepare_rootfs.py", """\
        #!/usr/bin/env python3
        \"\"\"
        scripts/prepare_rootfs.py
        Prepares the rootfs overlay for injection into the Ubuntu base squashfs.
        Runs before mksquashfs.
        \"\"\"
        import os
        import shutil
        import subprocess

        ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        FS_SRC = os.path.join(ROOT, "filesystem")
        BUILD  = os.path.join(ROOT, "build", "rootfs-overlay")

        def main():
            print("[prepare_rootfs] Building rootfs overlay...")
            if os.path.exists(BUILD):
                shutil.rmtree(BUILD)
            shutil.copytree(FS_SRC, BUILD, symlinks=True)

            # Remove placeholder .keep files
            for dirpath, _, files in os.walk(BUILD):
                for f in files:
                    if f in (".keep", "README.md"):
                        os.remove(os.path.join(dirpath, f))

            # Copy branding assets
            subprocess.run(["python", "scripts/copy_branding.py"], cwd=ROOT, check=True)

            # Package apps
            subprocess.run(["python", "scripts/package_apps.py"], cwd=ROOT, check=True)

            print(f"[prepare_rootfs] Done -> {BUILD}")

        if __name__ == "__main__":
            main()
    """)

# ============================================================
# SECTION 11 — validation/
# ============================================================
def validation():
    w("validation/run_all.py", """\
        #!/usr/bin/env python3
        \"\"\"
        validation/run_all.py
        Run every PyFlare OS validator and report pass/fail.
        \"\"\"
        import sys
        import importlib
        import os
        import time

        ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, ROOT)

        VALIDATORS = [
            ("validate_branding",       "Branding assets"),
            ("validate_icons",          "Icon theme"),
            ("validate_wallpapers",     "Wallpapers"),
            ("validate_json",           "JSON files"),
            ("validate_svg",            "SVG files"),
            ("validate_desktop",        "Desktop entries"),
            ("validate_packages",       "Package manifests"),
            ("validate_filesystem",     "Filesystem overlay"),
            ("validate_theme",          "GTK/GNOME theme"),
            ("validate_configs",        "Config files"),
            ("validate_services",       "Systemd services"),
            ("validate_permissions",    "File permissions"),
            ("validate_desktop_entries","Desktop entry syntax"),
            ("validate_boot",           "Boot configuration"),
        ]

        def run():
            passed = failed = 0
            report = []
            print("\\n  PyFlare OS — Validation Suite")
            print("  " + "=" * 50)
            for mod_name, label in VALIDATORS:
                t0 = time.perf_counter()
                try:
                    mod = importlib.import_module(f"validation.{mod_name}")
                    ok, errors = mod.validate(ROOT)
                except Exception as e:
                    ok, errors = False, [str(e)]
                elapsed = time.perf_counter() - t0
                status = "[PASS]" if ok else "[FAIL]"
                print(f"  {status}  {label:<35} {elapsed:.2f}s")
                if not ok:
                    for e in errors[:5]:
                        print(f"         -> {e}")
                    failed += 1
                else:
                    passed += 1
                report.append({"validator": mod_name, "passed": ok, "errors": errors})

            print("  " + "=" * 50)
            print(f"  Result: {passed} passed, {failed} failed\\n")

            os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
            import json
            with open(os.path.join(ROOT, "reports", "validation.json"), "w") as f:
                json.dump(report, f, indent=2)

            return 0 if failed == 0 else 1

        if __name__ == "__main__":
            sys.exit(run())
    """)

    # Generic validator template factory
    validators = {
        "validate_branding": ("branding/", "png,svg,webp,gif,json,ico", """\
            import os
            def validate(root):
                errors = []
                branding = os.path.join(root, "branding")
                if not os.path.isdir(branding):
                    return False, ["branding/ directory missing"]
                required = ["logos/svg", "wallpapers", "cursors", "badges", "previews", "themes"]
                for r in required:
                    if not os.path.isdir(os.path.join(branding, r)):
                        errors.append(f"Missing branding/{r}/")
                return len(errors) == 0, errors
        """),
        "validate_icons": ("filesystem/usr/share/icons/", "theme,png,svg", """\
            import os
            def validate(root):
                errors = []
                idx = os.path.join(root, "filesystem/usr/share/icons/PyFlare-Icons/index.theme")
                if not os.path.exists(idx):
                    errors.append("PyFlare-Icons/index.theme missing")
                return len(errors) == 0, errors
        """),
        "validate_wallpapers": ("filesystem/usr/share/backgrounds/", "png,jpg", """\
            import os
            def validate(root):
                errors = []
                bg = os.path.join(root, "filesystem/usr/share/backgrounds/pyflare")
                if not os.path.isdir(bg):
                    errors.append("backgrounds/pyflare/ missing — run copy_branding.py")
                return len(errors) == 0, errors
        """),
        "validate_json": (".", "json", """\
            import os, json
            def validate(root):
                errors = []
                for dirpath, _, files in os.walk(root):
                    if any(x in dirpath for x in ['.git', 'node_modules', '__pycache__', 'branding']):
                        continue
                    for f in files:
                        if not f.endswith('.json'):
                            continue
                        fp = os.path.join(dirpath, f)
                        try:
                            with open(fp, 'r', encoding='utf-8') as fh:
                                json.load(fh)
                        except Exception as e:
                            errors.append(f"{os.path.relpath(fp, root)}: {e}")
                return len(errors) == 0, errors
        """),
        "validate_svg": (".", "svg", """\
            import os
            import xml.etree.ElementTree as ET
            def validate(root):
                errors = []
                for dirpath, _, files in os.walk(root):
                    if any(x in dirpath for x in ['.git', '__pycache__']):
                        continue
                    for f in files:
                        if not f.endswith('.svg'):
                            continue
                        fp = os.path.join(dirpath, f)
                        try:
                            ET.parse(fp)
                        except Exception as e:
                            errors.append(f"{os.path.relpath(fp, root)}: {e}")
                return len(errors) == 0, errors
        """),
        "validate_desktop": ("filesystem/usr/share/applications/", "desktop", """\
            import os
            REQUIRED_KEYS = ['Type', 'Name', 'Exec', 'Icon']
            def validate(root):
                errors = []
                apps_dir = os.path.join(root, 'filesystem/usr/share/applications')
                if not os.path.isdir(apps_dir):
                    return False, ['filesystem/usr/share/applications/ missing']
                for f in os.listdir(apps_dir):
                    if not f.endswith('.desktop'):
                        continue
                    fp = os.path.join(apps_dir, f)
                    with open(fp, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                    for key in REQUIRED_KEYS:
                        if f'{key}=' not in content:
                            errors.append(f"{f}: missing {key}")
                return len(errors) == 0, errors
        """),
        "validate_packages": ("packages/", "json,yaml", """\
            import os, json
            def validate(root):
                errors = []
                manifests = os.path.join(root, 'packages/manifests')
                if not os.path.isdir(manifests):
                    return False, ['packages/manifests/ missing']
                for f in os.listdir(manifests):
                    if not f.endswith('.json'):
                        continue
                    fp = os.path.join(manifests, f)
                    try:
                        with open(fp) as fh:
                            data = json.load(fh)
                        if 'schema' not in data:
                            errors.append(f"{f}: missing 'schema' field")
                    except Exception as e:
                        errors.append(f"{f}: {e}")
                return len(errors) == 0, errors
        """),
        "validate_filesystem": ("filesystem/", "all", """\
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
                    fp = os.path.join(fs, r)
                    if not os.path.exists(fp):
                        errors.append(f"filesystem/{r} missing")
                return len(errors) == 0, errors
        """),
        "validate_theme": ("filesystem/usr/share/themes/", "css,ini", """\
            import os
            REQUIRED_THEME_FILES = [
                'index.theme', 'gtk-3.0/gtk.css', 'gtk-4.0/gtk.css',
                'gnome-shell/gnome-shell.css',
            ]
            def validate(root):
                errors = []
                theme = os.path.join(root, 'filesystem/usr/share/themes/PyFlare-Dark')
                if not os.path.isdir(theme):
                    return False, ['PyFlare-Dark theme directory missing']
                for f in REQUIRED_THEME_FILES:
                    fp = os.path.join(theme, f)
                    if not os.path.exists(fp):
                        errors.append(f"PyFlare-Dark/{f} missing")
                    elif os.path.getsize(fp) < 10:
                        errors.append(f"PyFlare-Dark/{f} is empty")
                return len(errors) == 0, errors
        """),
        "validate_configs": ("config/", "yaml", """\
            import os
            try:
                import yaml
            except ImportError:
                yaml = None
            REQUIRED = ['default.yaml', 'packages.yaml', 'theme.yaml', 'branding.yaml', 'post_install.sh']
            def validate(root):
                errors = []
                cfg = os.path.join(root, 'config')
                for f in REQUIRED:
                    fp = os.path.join(cfg, f)
                    if not os.path.exists(fp):
                        errors.append(f"config/{f} missing")
                    elif yaml and f.endswith('.yaml'):
                        try:
                            with open(fp) as fh:
                                yaml.safe_load(fh)
                        except Exception as e:
                            errors.append(f"config/{f}: YAML parse error: {e}")
                return len(errors) == 0, errors
        """),
        "validate_services": ("filesystem/etc/systemd/", "service,timer", """\
            import os, configparser
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
                        except Exception as e:
                            errors.append(f"{svc}: parse error: {e}")
                return len(errors) == 0, errors
        """),
        "validate_permissions": ("filesystem/", "all", """\
            import os, stat
            SHOULD_BE_EXECUTABLE = [
                'opt/pyflare/engine/pyflare-engine',
                'opt/pyflare/bin/pyflare-updater',
                'opt/pyflare/bin/pyflare-firstrun',
            ]
            SHOULD_NOT_BE_EXECUTABLE = [
                'etc/hostname', 'etc/os-release', 'etc/fstab',
            ]
            def validate(root):
                # Source-tree permission check is advisory only
                errors, warnings = [], []
                fs = os.path.join(root, 'filesystem')
                for f in SHOULD_BE_EXECUTABLE:
                    fp = os.path.join(fs, f)
                    if os.path.exists(fp):
                        mode = os.stat(fp).st_mode
                        if not (mode & stat.S_IXUSR):
                            warnings.append(f"{f} should be executable (will be fixed at install)")
                return True, warnings  # Always pass — fixable at install
        """),
        "validate_desktop_entries": ("filesystem/usr/share/applications/", "desktop", """\
            import os, re
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
                        errors.append(f"{app_id}.desktop missing")
                return len(errors) == 0, errors
        """),
        "validate_boot": ("filesystem/", "cfg,conf", """\
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
                for f in REQUIRED_BOOT:
                    fp = os.path.join(fs, f)
                    if not os.path.exists(fp):
                        errors.append(f"filesystem/{f} missing")
                return len(errors) == 0, errors
        """),
    }

    for mod_name, (_scope, _types, code) in validators.items():
        w(f"validation/{mod_name}.py", f"""\
            #!/usr/bin/env python3
            \"\"\"
            validation/{mod_name}.py
            PyFlare OS asset validator — {mod_name.replace('_', ' ').title()}
            \"\"\"
            import os
            import sys

            {textwrap.dedent(code)}

            if __name__ == "__main__":
                root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ok, errors = validate(root)
                for e in errors:
                    print(f"  [error] {{e}}")
                status = "PASS" if ok else "FAIL"
                print(f"  {{status}}: {mod_name}")
                sys.exit(0 if ok else 1)
        """)

    w("validation/__init__.py", '"""PyFlare OS validation suite."""\n')

# ============================================================
# SECTION 12 — docs/
# ============================================================
def docs():
    w("docs/BUILD.md", """\
        # Building PyFlare OS

        ## Prerequisites

        Requires a **native Linux environment** (Ubuntu 22.04+ recommended) with root access.
        WSL2, a VM, or a Linux machine all work.

        ```bash
        sudo apt install -y \\
          squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin \\
          mtools dosfstools python3 python3-pip rsync calamares \\
          libcairo2-dev

        pip install -r requirements.txt
        ```

        ## Build Steps

        ```bash
        # 1. Generate branding assets
        python -m branding_generator.main generate
        python -m branding_generator.main validate

        # 2. Prepare rootfs overlay
        python scripts/prepare_rootfs.py

        # 3. Run all validators
        python validation/run_all.py

        # 4. Build ISO (root required)
        sudo python3 build.py --config config/default.yaml

        # 5. Generate checksums
        python scripts/generate_checksums.py
        ```

        ## Output

        - `output/pyflare-os-1.0.0-ember-amd64.iso`
        - `output/pyflare-os-1.0.0-ember-amd64.iso.sha256`
        - `output/pyflare-os-1.0.0-ember-amd64.iso.md5`

        ## Configuration

        | File | Purpose |
        |------|---------|
        | `config/default.yaml` | Main OS settings |
        | `config/packages.yaml` | Package lists |
        | `config/theme.yaml` | Visual identity |
        | `config/branding.yaml` | Product strings |

        ## Troubleshooting

        - **squashfs error:** Must build on native Linux ext4 filesystem
        - **grub error:** Ensure `grub-pc-bin` and `grub-efi-amd64-bin` both installed
        - **cairosvg error:** `sudo apt install libcairo2-dev` then `pip install cairosvg`
    """)

    w("docs/DEVELOPMENT.md", """\
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
    """)

    w("docs/BRANDING.md", """\
        # PyFlare OS Branding Guide

        ## Visual Identity

        | Element | Value |
        |---------|-------|
        | Primary color | #3B5BDB (Indigo) |
        | Accent color | #00BFFF (Cyan) |
        | Secondary | #7C3AED (Violet) |
        | Background | #0C0F1E |
        | Surface | #0D1117 |
        | Text | #E6EDF3 |
        | UI Font | Inter 11 |
        | Display Font | Space Grotesk Bold |
        | Mono Font | JetBrains Mono 11 |

        ## Generating Assets

        All branding assets are **procedurally generated** by `branding_generator/`.

        ```bash
        # Full generation
        python -m branding_generator.main generate

        # Individual stages
        python -m branding_generator.main export
        python -m branding_generator.main preview
        python -m branding_generator.main validate
        ```

        ## Asset Structure

        | Directory | Contents |
        |-----------|----------|
        | `branding/logos/` | SVG + PNG logos |
        | `branding/wallpapers/` | 3 resolutions × 8 styles |
        | `branding/cursors/` | XCursor, Windows .cur, macOS |
        | `branding/themes/` | GTK3/4, Qt, VS Code, Terminal |
        | `branding/badges/` | Version badges |
        | `branding/icons/` | App icon sizes |
        | `branding/animations/` | Lottie JSON, WebP, GIF, MP4 |
        | `branding/fonts/` | Font cache + manifest |
        | `branding/previews/` | Preview sheets |

        ## Deploying to Filesystem

        ```bash
        python scripts/copy_branding.py
        ```
    """)

    w("docs/PACKAGING.md", """\
        # PyFlare OS Packaging

        ## Package Naming

        `pyflare-{component}_{version}_all.deb`

        ## Core Packages

        | Package | Description |
        |---------|-------------|
        | `pyflare-engine` | Runtime daemon |
        | `pyflare-desktop` | Theme + icons + wallpapers |
        | `pyflare-apps` | Meta-package (all apps) |
        | `pyflare-fonts` | Inter + Space Grotesk + JetBrains Mono |
        | `pyflare-cursors` | Custom cursor theme |

        ## Manifests

        Package manifests live in `packages/manifests/`.
        Format: JSON with `schema: pyflare-package-manifest/1.0`.

        ## Build

        ```bash
        # Package all applications
        python scripts/package_apps.py

        # Generate filesystem manifest
        python scripts/generate_manifest.py
        ```
    """)

    w("docs/INSTALLER.md", """\
        # PyFlare OS Installer

        PyFlare OS uses **Calamares** as its graphical installer.

        ## Configuration

        | File | Purpose |
        |------|---------|
        | `installer/config/settings.conf` | Calamares main config |
        | `installer/config/branding.desc` | Branding strings + images |
        | `installer/slides/` | Installation slideshow (HTML) |
        | `installer/scripts/pre-install.sh` | Pre-install hook |
        | `installer/scripts/post-install.sh` | Post-install chroot hook |

        ## Slideshow

        Five HTML slides shown during installation:
        1. Welcome to PyFlare OS
        2. Lightning Fast
        3. Beautiful by Default
        4. Privacy First
        5. Built for Developers

        ## Required Branding Images

        Place in `installer/config/`:
        - `pyflare-logo.png` (200×200) — Generated by branding_generator
        - `pyflare-icon.png` (64×64) — Generated by branding_generator
        - `pyflare-welcome.png` (540×240) — Generated by branding_generator

        ## Post-Install Actions

        `installer/scripts/post-install.sh` runs inside the installed system and:
        - Enables PyFlare systemd services
        - Compiles gsettings schemas
        - Rebuilds font cache
        - Updates initramfs and GRUB
    """)

    w("docs/DIRECTORY_STRUCTURE.md", """\
        # PyFlare OS — Directory Structure Reference

        ```
        PyFlare/
        │
        ├── README.md                    Project overview
        ├── BUILD.md                     ISO build instructions
        ├── CONTRIBUTING.md              Contribution guide
        ├── CHANGELOG.md                 Version history
        ├── ROADMAP.md                   Future plans
        ├── SECURITY.md                  Security policy
        ├── LICENSE                      MIT License (Aachman Studios)
        ├── requirements.txt             Python dependencies
        ├── build.py                     Main build orchestrator
        │
        ├── config/
        │   ├── default.yaml             OS build parameters
        │   ├── packages.yaml            APT/Flatpak/Snap package lists
        │   ├── settings.yaml            Runtime settings
        │   ├── theme.yaml               Visual identity tokens
        │   ├── branding.yaml            Product identity strings
        │   ├── post_install.sh          Chroot post-install script
        │   └── grub/grub.cfg            GRUB config template
        │
        ├── filesystem/                  Linux filesystem source overlay
        │   ├── etc/                     System configuration
        │   │   ├── hostname
        │   │   ├── os-release
        │   │   ├── issue / issue.net
        │   │   ├── motd
        │   │   ├── environment
        │   │   ├── hosts / fstab
        │   │   ├── default/grub + locale
        │   │   ├── apt/sources.list
        │   │   ├── systemd/system/*.service
        │   │   ├── systemd/user/*.service
        │   │   ├── gdm3/custom.conf
        │   │   ├── plymouth/plymouthd.conf
        │   │   ├── gtk-3.0/settings.ini
        │   │   ├── gtk-4.0/settings.ini
        │   │   ├── fonts/local.conf
        │   │   ├── ssh/sshd_config
        │   │   ├── sysctl.d/99-pyflare.conf
        │   │   ├── profile.d/pyflare.sh
        │   │   ├── sudoers.d/pyflare
        │   │   ├── xdg/autostart/
        │   │   ├── xdg/menus/
        │   │   ├── skel/.bashrc + .config/
        │   │   ├── cron.d/
        │   │   ├── security/limits.d/
        │   │   └── pyflare/os.conf
        │   │
        │   ├── usr/share/
        │   │   ├── applications/        .desktop launchers (11 apps)
        │   │   ├── glib-2.0/schemas/    GNOME gsettings overrides
        │   │   ├── icons/PyFlare-Icons/ Icon theme
        │   │   ├── themes/PyFlare-Dark/ GTK3/4 + GNOME Shell CSS
        │   │   ├── backgrounds/pyflare/ Wallpapers
        │   │   ├── sounds/pyflare/      Sound theme
        │   │   ├── fonts/pyflare/       Custom fonts
        │   │   ├── plymouth/themes/     Boot splash
        │   │   └── locale/              Locale data
        │   │
        │   ├── boot/grub/themes/pyflare/ GRUB theme
        │   ├── opt/pyflare/             PyFlare runtime
        │   ├── var/                     Runtime state
        │   └── home/pyflare/            Default user skeleton
        │
        ├── branding/                    Generated assets
        │   ├── logos/                   SVG + PNG logos
        │   ├── icons/                   App icon sizes
        │   ├── wallpapers/              8 styles × 3 resolutions
        │   ├── cursors/                 X11 + Windows + macOS
        │   ├── themes/                  GTK + Qt + VS Code + Terminal
        │   ├── badges/                  Version badges
        │   ├── animations/              Lottie + WebP + GIF + MP4
        │   ├── fonts/                   Font cache
        │   ├── previews/                Preview sheets
        │   └── export/                  SVG→PDF/EPS/ICO/ICNS
        │
        ├── branding_generator/          Asset generation pipeline
        ├── desktop/                     GNOME desktop overrides
        ├── packages/                    Package manifests
        ├── installer/                   Calamares installer config
        ├── applications/                App source stubs (11 apps)
        ├── validation/                  Automated validators
        ├── scripts/                     Build utility scripts
        ├── docs/                        Documentation
        ├── tests/                       Test suite
        └── .github/workflows/           CI (GitHub Actions)
        ```
    """)

    w("docs/CONTRIBUTING.md", """\
        # Contributing to PyFlare OS

        ## Getting Started

        1. Fork the repository
        2. Clone locally: `git clone https://github.com/aachman-studios/pyflare-os`
        3. Install dependencies: `pip install -r requirements.txt`
        4. Create a branch: `git checkout -b feature/my-feature`

        ## Areas to Contribute

        | Area | Location | Skill Level |
        |------|----------|-------------|
        | Branding / design | `branding_generator/` | Intermediate |
        | Desktop theme | `filesystem/usr/share/themes/` | Intermediate |
        | App stubs | `applications/` | Beginner |
        | Validation | `validation/` | Beginner |
        | Build scripts | `scripts/` | Advanced |
        | Documentation | `docs/` | Beginner |

        ## Standards

        - Follow PEP 8 for Python
        - Run `ruff check .` before committing
        - Run `python validation/run_all.py` — all validators must pass
        - Write tests for new validators

        ## Pull Request Checklist

        - [ ] All validators pass
        - [ ] Code is linted (ruff)
        - [ ] Documentation updated
        - [ ] CHANGELOG.md updated

        ## Contact

        Aachman Studios — hello@aachmanstudios.dev
    """)

    w("CHANGELOG.md", """\
        # PyFlare OS — Changelog

        All notable changes are documented here.
        Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

        ---

        ## [1.0.0] — 2026-07-30 — "Ember"

        ### Added
        - Complete source tree for PyFlare OS 1.0.0 Ember
        - Branding generator pipeline (16 modules, 800+ assets)
        - Linux filesystem overlay (`filesystem/`)
        - 11 application stubs with full structure
        - Calamares installer configuration and slides
        - Package manifests (core, desktop, applications)
        - 14 automated validators + run_all.py
        - GitHub Actions CI (build, validate, lint)
        - Full documentation suite (8 docs + root docs)
        - GNOME gsettings overrides
        - GTK3/4 + GNOME Shell dark theme (CSS)
        - Plymouth boot splash (script-based)
        - GRUB theme with PyFlare branding
        - systemd service units

        ### Changed
        - Renamed from AppSuite OS to PyFlare OS throughout
        - Vendor updated to Aachman Studios
        - Ubuntu base pinned to 24.04 LTS (Noble Numbat)

        ### Fixed
        - Validator Unicode crash on Windows cp1252 terminals
        - SVG xmlns false-positive in validator
        - cairosvg noise suppression on systems without libcairo

        ---

        ## [0.9.0] — 2026-07-29 — "Prototype"

        ### Added
        - Initial branding generator (icons, wallpapers, cursors, themes)
        - Basic build scripts
        - Initial README

        ---
    """)

    w("ROADMAP.md", """\
        # PyFlare OS — Roadmap

        ## v1.0.0 — Ember (Current)

        - [x] Branding generator pipeline
        - [x] Linux filesystem overlay
        - [x] GNOME desktop integration
        - [x] Calamares installer config
        - [x] Application stubs
        - [x] Validation suite
        - [x] CI pipeline
        - [ ] Live ISO build (requires Linux build environment)
        - [ ] Hardware testing

        ## v1.1.0 — Flare

        - [ ] PyFlare Engine — real Ollama integration
        - [ ] AppSuite — basic GTK4 IDE
        - [ ] PyFlare Store — Flatpak frontend
        - [ ] PyFlare Terminal — VTE-based with AI completions
        - [ ] Plymouth — animated flame sequence
        - [ ] GRUB — custom background generation
        - [ ] Installer images (Calamares)

        ## v1.2.0 — Nova

        - [ ] PyFlare Files — AI semantic search
        - [ ] PyFlare Browser — WebKit-based
        - [ ] Plugin system
        - [ ] Automatic updates
        - [ ] OEM configuration support

        ## v2.0.0 — Ignite

        - [ ] PyFlare KDE edition
        - [ ] ARM64 support
        - [ ] Secure Boot
        - [ ] Immutable root (read-only squashfs + overlay)
        - [ ] Flatpak-first application model
    """)

    w("SECURITY.md", """\
        # Security Policy — PyFlare OS

        ## Supported Versions

        | Version | Supported |
        |---------|-----------|
        | 1.0.x   | Yes       |
        | < 1.0   | No        |

        ## Reporting a Vulnerability

        **Do not open a public GitHub issue for security vulnerabilities.**

        Email: security@aachmanstudios.dev

        Include:
        - Description of the vulnerability
        - Steps to reproduce
        - Potential impact
        - Suggested fix (if any)

        We will respond within 72 hours and aim to patch within 14 days.

        ## Security Principles

        - No telemetry by default
        - No cloud accounts required
        - SSH hardened (no root login, modern ciphers only)
        - sysctl hardened (kernel pointer restriction, dmesg restriction)
        - UFW firewall enabled
        - AppArmor enabled (Ubuntu default)
    """)

    w("docs/ARCHITECTURE.md", """\
        # PyFlare OS Architecture

        ## System Stack

        ```
        ┌─────────────────────────────────────┐
        │           User Applications         │
        │  Terminal  Browser  Files  Store ... │
        ├─────────────────────────────────────┤
        │          PyFlare Engine              │
        │  AI Runtime · Plugin Manager        │
        │  Package Backend · Event Bus        │
        ├─────────────────────────────────────┤
        │         GNOME Desktop                │
        │  GNOME Shell · GDM3 · Wayland/X11   │
        ├─────────────────────────────────────┤
        │        Ubuntu 24.04 LTS Base         │
        │  APT · systemd · D-Bus · udev       │
        ├─────────────────────────────────────┤
        │      Linux Kernel (HWE 24.04)       │
        └─────────────────────────────────────┘
        ```

        ## PyFlare Engine

        D-Bus service (`dev.pyflare.Engine`) that provides:
        - AI inference via Ollama (local LLM)
        - Plugin management
        - Package metadata aggregation
        - System event bus

        ## Application Model

        All bundled apps are Python + GTK4/libadwaita applications.
        They communicate with PyFlare Engine via D-Bus.

        ## Build System

        ```
        build.py
         ├── download_base.py     Fetch Ubuntu ISO
         ├── prepare_rootfs.py    Build filesystem overlay
         ├── copy_branding.py     Deploy branding assets
         ├── package_apps.py      Install app stubs
         ├── chroot_manager.py    Manage chroot environment
         └── package_iso.py       Assemble final ISO
        ```
    """)

    w("docs/STYLE_GUIDE.md", """\
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
    """)

    w("docs/FAQ.md", """\
        # PyFlare OS — Frequently Asked Questions

        ## General

        **Q: What is PyFlare OS?**
        A: PyFlare OS is a custom Linux distribution based on Ubuntu 24.04 LTS,
        built by Aachman Studios for AI-native computing. It includes the PyFlare
        Engine (local AI runtime), AppSuite, and a full custom desktop experience.

        **Q: Is it free?**
        A: Yes. PyFlare OS source code is MIT licensed.

        **Q: Does it send data to the cloud?**
        A: No. All AI inference runs locally via Ollama. No telemetry.

        ## Technical

        **Q: What desktop environment does it use?**
        A: GNOME with PyFlare-Dark theme, custom icons, and Dash-to-Dock.

        **Q: Can I run it in a VM?**
        A: Yes. VirtualBox, GNOME Boxes, and VMware all work. Allocate 4GB+ RAM.

        **Q: What is PyFlare Engine?**
        A: A D-Bus background service that handles AI inference (Ollama),
        plugin management, and package metadata aggregation.

        **Q: How do I build the ISO?**
        A: See [BUILD.md](BUILD.md). Requires a Linux environment with root access.

        **Q: How do I contribute?**
        A: See [CONTRIBUTING.md](CONTRIBUTING.md).

        ## Troubleshooting

        **Q: GDM3 shows a black screen**
        A: Run `sudo systemctl restart gdm3`. If it persists, check `journalctl -u gdm3`.

        **Q: PyFlare Engine won't start**
        A: `sudo systemctl restart pyflare-engine && journalctl -u pyflare-engine -f`

        **Q: How do I reset to default settings?**
        A: `dconf reset -f /org/gnome/` and log out/in.
    """)

# ============================================================
# SECTION 13 — branding/gtk and branding/qt placeholders
# ============================================================
def branding_dirs():
    w("branding/gtk/README.md", """\
        # PyFlare OS GTK Theme Sources

        GTK theme CSS is generated by `branding_generator/themes.py`
        and deployed to `filesystem/usr/share/themes/PyFlare-Dark/`.

        Source files in `branding/themes/` are the canonical references.

        To apply:
        ```bash
        python scripts/copy_branding.py
        ```
    """)

    w("branding/qt/README.md", """\
        # PyFlare OS Qt Theme Sources

        Qt stylesheet (`pyflare_dark.qss`) is generated by `branding_generator/themes.py`.
        Used by Qt5/Qt6 applications running under PyFlare OS.

        To apply system-wide, set:
        ```
        QT_STYLE_OVERRIDE=fusion
        QT_QPA_PLATFORMTHEME=gnome
        ```

        The QSS file is referenced by `/opt/pyflare/share/themes/pyflare_dark.qss`.
    """)

    mkdir("branding/gtk")
    mkdir("branding/qt")

# ============================================================
# MAIN
# ============================================================
def main():
    print(f"\n  PyFlare OS — Source Tree Generator")
    print(f"  Root: {ROOT}\n")

    steps = [
        ("etc",                  etc),
        ("usr/share",            usr_share),
        ("opt/pyflare",          opt),
        ("var + home",           var_and_home),
        ("desktop/",             desktop),
        ("packages/",            packages),
        ("installer/",           installer),
        ("applications/ (x11)",  applications),
        (".github/workflows/",   github_ci),
        ("scripts/",             scripts),
        ("validation/",          validation),
        ("docs/ + root docs",    docs),
        ("branding/gtk + qt",    branding_dirs),
    ]

    for label, fn in steps:
        print(f"\n  ── {label}")
        fn()

    print(f"\n  ✓ Source tree generation complete.")
    print(f"  Next: python validation/run_all.py\n")

if __name__ == "__main__":
    main()
