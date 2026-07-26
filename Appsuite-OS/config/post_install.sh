#!/bin/bash
# This script runs inside the chroot environment after APT packages are installed.
# Use this to configure system settings, users, and branding.

set -e

echo "==> Running post-install configurations..."

# Set up locale and timezone
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8
ln -fs /usr/share/zoneinfo/Etc/UTC /etc/localtime
dpkg-reconfigure -f noninteractive tzdata

# Create default live user if doesn't exist
if ! id -u appsuite >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo,cdrom,dip,plugdev,render,video appsuite
    echo "appsuite:password" | chpasswd
fi

# Enable auto-login for live session (GDM3 example)
if [ -d /etc/gdm3 ]; then
    cat <<EOF > /etc/gdm3/custom.conf
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=appsuite
EOF
fi

# Set hostname
echo "appsuite-os" > /etc/hostname

# Update initramfs to apply plymouth/graphics changes
update-initramfs -u -k all

echo "==> Post-install complete."
