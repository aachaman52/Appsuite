#!/usr/bin/env bash
# config/post_install.sh
# PyFlare OS — Post-installation chroot script
# Runs inside the Ubuntu chroot after all packages are installed.
# Must be idempotent.

set -euo pipefail

PYFLARE_VERSION="1.0.0"
PYFLARE_CODENAME="Ember"
PYFLARE_USER="pyflare"

echo "[PyFlare] Running post-install configuration (v${PYFLARE_VERSION} ${PYFLARE_CODENAME})"

# ============================================================
# SYSTEM IDENTITY
# ============================================================
echo "pyflare" > /etc/hostname

cat > /etc/os-release << 'EOF'
NAME="PyFlare OS"
VERSION="1.0.0 (Ember)"
ID=pyflare
ID_LIKE=ubuntu
PRETTY_NAME="PyFlare OS 1.0.0 Ember"
VERSION_ID="1.0.0"
VERSION_CODENAME="ember"
HOME_URL="https://pyflare.dev"
SUPPORT_URL="https://pyflare.dev/support"
BUG_REPORT_URL="https://github.com/pyflare/pyflare-os/issues"
PRIVACY_POLICY_URL="https://pyflare.dev/privacy"
UBUNTU_CODENAME="noble"
EOF

cat > /etc/issue << 'EOF'
PyFlare OS 1.0.0 Ember \n \l
EOF

cat > /etc/motd << 'EOF'

  ██████╗ ██╗   ██╗███████╗██╗      █████╗ ██████╗ ███████╗
  ██╔══██╗╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██╔══██╗██╔════╝
  ██████╔╝ ╚████╔╝ █████╗  ██║     ███████║██████╔╝█████╗
  ██╔═══╝   ╚██╔╝  ██╔══╝  ██║     ██╔══██║██╔══██╗██╔══╝
  ██║        ██║   ██║     ███████╗██║  ██║██║  ██║███████╗
  ╚═╝        ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
  OS v1.0.0 Ember — The AI-Native Linux Distribution

EOF

# ============================================================
# DEFAULT USER SETUP
# ============================================================
if ! id "${PYFLARE_USER}" &>/dev/null; then
    useradd -m -s /bin/bash -G sudo,audio,video,plugdev,netdev "${PYFLARE_USER}"
    echo "${PYFLARE_USER}:pyflare" | chpasswd
    # Force password change on first login
    chage -d 0 "${PYFLARE_USER}"
fi

# ============================================================
# PLYMOUTH BOOT SPLASH
# ============================================================
if command -v update-alternatives &>/dev/null; then
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth \
        default.plymouth /usr/share/plymouth/themes/pyflare/pyflare.plymouth 100 || true
    update-alternatives --set default.plymouth \
        /usr/share/plymouth/themes/pyflare/pyflare.plymouth || true
fi

# Update initramfs with Plymouth theme
if command -v update-initramfs &>/dev/null; then
    update-initramfs -u || true
fi

# ============================================================
# GRUB CONFIGURATION
# ============================================================
cat > /etc/default/grub << 'EOF'
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_TIMEOUT_STYLE=countdown
GRUB_DISTRIBUTOR="PyFlare OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 vt.global_cursor_default=0"
GRUB_CMDLINE_LINUX=""
GRUB_BACKGROUND="/usr/share/grub/themes/pyflare/background.png"
GRUB_THEME="/boot/grub/themes/pyflare/theme.txt"
GRUB_GFXMODE="1920x1080,auto"
GRUB_GFXPAYLOAD_LINUX="keep"
EOF

if command -v update-grub &>/dev/null; then
    update-grub || true
fi

# ============================================================
# GNOME DEFAULTS VIA DCONF
# ============================================================
if command -v dconf &>/dev/null; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/dbus/system_bus_socket"

    # Apply system-wide gsettings overrides
    mkdir -p /usr/share/glib-2.0/schemas/
    cat > /usr/share/glib-2.0/schemas/99-pyflare.gschema.override << 'EOF2'
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

[org.gnome.desktop.background]
picture-uri='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
picture-uri-dark='file:///usr/share/backgrounds/pyflare/default_dark_4K.png'
picture-options='zoom'
primary-color='#0C0F1E'

[org.gnome.desktop.screensaver]
picture-uri='file:///usr/share/backgrounds/pyflare/minimal_dark_4K.png'
primary-color='#0C0F1E'

[org.gnome.shell]
enabled-extensions=['dash-to-dock@micxgx.gmail.com','user-theme@gnome-shell-extensions.gcampax.github.com','blur-my-shell@aunetx','just-perfection-desktop@just-perfection']
favorite-apps=['pyflare-files.desktop','pyflare-terminal.desktop','pyflare-browser.desktop','pyflare-store.desktop','pyflare-settings.desktop','pyflare-ai.desktop']

[org.gnome.shell.extensions.dash-to-dock]
dock-position='BOTTOM'
dash-max-icon-size=48
show-trash=false
show-mounts=false
transparency-mode='FIXED'
background-opacity=0.85
custom-background-color=true
background-color='#0D1117'

[org.gnome.desktop.wm.preferences]
button-layout='appmenu:minimize,maximize,close'
theme='PyFlare-Dark'

[org.gnome.desktop.session]
idle-delay=uint32 300
EOF2

    glib-compile-schemas /usr/share/glib-2.0/schemas/ || true
fi

# ============================================================
# FONT CONFIGURATION
# ============================================================
if command -v fc-cache &>/dev/null; then
    fc-cache -fv || true
fi

# ============================================================
# FLATPAK SETUP
# ============================================================
if command -v flatpak &>/dev/null; then
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo || true
fi

# ============================================================
# SYSTEMD SERVICES
# ============================================================
systemctl enable NetworkManager || true
systemctl enable gdm3 || true
systemctl enable pyflare-firstrun.service || true
systemctl disable apport.service || true
systemctl mask whoopsie.service || true

# ============================================================
# CLEANUP
# ============================================================
apt-get autoremove -y
apt-get clean
rm -rf /tmp/* /var/tmp/*
find /var/log -type f -name "*.log" -delete
find /var/log -type f -name "*.gz" -delete
history -c

echo "[PyFlare] Post-install complete."
