#!/bin/sh
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
