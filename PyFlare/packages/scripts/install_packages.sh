#!/usr/bin/env bash
# PyFlare OS — Package Installation Script
set -euo pipefail

echo "[PyFlare] Updating APT package index..."
apt-get update -q

echo "[PyFlare] Installing 150 base packages..."
apt-get install -y --no-install-recommends ubuntu-standard ubuntu-minimal linux-generic-hwe-24.04 linux-headers-generic-hwe-24.04 initramfs-tools grub-pc grub-efi-amd64 grub-efi-amd64-signed shim-signed efibootmgr os-prober systemd systemd-resolved systemd-timesyncd udev dbus polkit udisks2 upower acpid gnome-shell gnome-session gnome-control-center gnome-tweaks gnome-shell-extensions gdm3 gvfs gvfs-backends nautilus nautilus-extension-gnome-terminal gnome-terminal gnome-disk-utility gnome-system-monitor gnome-calculator gnome-text-editor gnome-screenshot gnome-keyring libpam-gnome-keyring seahorse baobab evince eog file-roller gedit cheese totem rhythmbox simple-scan xorg xserver-xorg-core xserver-xorg-input-libinput mesa-utils libgl1-mesa-dri libgles2-mesa vulkan-tools libvulkan1 nvidia-driver-535 amdgpu-pro intel-media-va-driver plymouth plymouth-themes plymouth-theme-spinner pipewire pipewire-alsa pipewire-pulse pipewire-jack wireplumber pavucontrol alsa-utils network-manager network-manager-gnome network-manager-openvpn network-manager-openvpn-gnome wireless-tools wpasupplicant curl wget openssh-client openssh-server nftables ufw avahi-daemon fonts-noto fonts-noto-cjk fonts-noto-color-emoji fonts-liberation fonts-ubuntu fonts-freefont-ttf fontconfig cups system-config-printer printer-driver-gutenprint git git-lfs python3 python3-pip python3-venv python3-dev python3-setuptools python3-wheel build-essential cmake make gcc g++ clang lldb gdb valgrind strace pkg-config libssl-dev libffi-dev libsqlite3-dev jq tree tmux htop neofetch unzip zip p7zip-full docker.io docker-compose containerd flatpak gnome-software-plugin-flatpak python3-pil python3-numpy python3-requests python3-yaml python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-dev vim nano less man-db bash-completion command-not-found software-properties-common apt-transport-https ca-certificates gnupg lsb-release debconf-utils gdebi synaptic timeshift

echo "[PyFlare] Setting up Flatpak & Snaps..."
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo || true

echo "[PyFlare] Package installation complete."
