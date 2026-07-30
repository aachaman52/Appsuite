# PyFlare profile.d — sets environment for all login shells
# /etc/profile.d/pyflare.sh

export PYFLARE_HOME="/opt/pyflare"
export PYFLARE_VERSION="1.0.0"
export PYFLARE_CODENAME="Ember"
export PYFLARE_DATA="/var/lib/pyflare"
export PYFLARE_CONFIG="/etc/pyflare"
export PYFLARE_LOG="/var/log/pyflare"

# Add PyFlare binaries to PATH
if [ -d "/opt/pyflare/bin" ]; then
    export PATH="/opt/pyflare/bin:$PATH"
fi

# GTK theming
export GTK_THEME="PyFlare-Dark"

# QT theming (if Qt apps are installed)
export QT_QPA_PLATFORMTHEME="gnome"
export QT_STYLE_OVERRIDE="fusion"

# Aliases
alias pyflare-status="systemctl status pyflare-engine"
alias pyflare-logs="journalctl -u pyflare-engine -f"
alias pyflare-update="pkexec /opt/pyflare/bin/pyflare-updater"

# Neofetch info (if installed)
if command -v neofetch >/dev/null 2>&1; then
    neofetch --ascii_distro PyFlare 2>/dev/null || neofetch 2>/dev/null || true
fi
