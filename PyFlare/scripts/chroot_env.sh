#!/bin/bash
set -e

SQUASHFS_DIR="$BUILD_DIR/squashfs-root"

echo "Setting up chroot environment..."
cp /etc/resolv.conf "$SQUASHFS_DIR/etc/resolv.conf"

# Copy in configuration files
cp "$BASE_DIR/config/post_install.sh" "$SQUASHFS_DIR/tmp/post_install.sh"
chmod +x "$SQUASHFS_DIR/tmp/post_install.sh"

# Extract packages list using python
PACKAGES=$(python3 -c "import yaml; print(' '.join(yaml.safe_load(open('$BASE_DIR/config/packages.yaml'))['packages']))")
REPOS=$(python3 -c "import yaml; repos=yaml.safe_load(open('$BASE_DIR/config/packages.yaml')).get('repositories', []); print('\n'.join(repos))")

# Create a chroot setup script
cat <<EOF > "$SQUASHFS_DIR/tmp/setup.sh"
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devpts none /dev/pts

echo "Adding Repositories..."
for repo in $REPOS; do
    add-apt-repository -y "\$repo"
done

apt-get update
apt-get install -y $PACKAGES

/tmp/post_install.sh

apt-get clean
rm -rf /tmp/* ~/.bash_history
umount /proc || true
umount /sys || true
umount /dev/pts || true
EOF

chmod +x "$SQUASHFS_DIR/tmp/setup.sh"

echo "Entering chroot to install packages and configure OS..."
chroot "$SQUASHFS_DIR" /tmp/setup.sh

rm -f "$SQUASHFS_DIR/tmp/setup.sh"
rm -f "$SQUASHFS_DIR/tmp/post_install.sh"
echo "Chroot setup complete."
