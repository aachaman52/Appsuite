# Customization

AppSuite OS is fully modular. To customize the OS:

## Adding Software
Edit `config/packages.yaml` and add Debian packages to the `packages` array. To add a custom repository, append it to `repositories`.

## Boot Splash (Plymouth)
Place Plymouth themes in `branding/plymouth/`. The `post_install.sh` script can be modified to update the default theme using `update-alternatives --set default.plymouth /path/to/theme.plymouth`.

## Desktop Wallpapers
Place wallpapers in `branding/wallpapers/`. During the chroot step, you can modify `post_install.sh` to copy these images into `/usr/share/backgrounds/` and map them to the default dconf schema for GNOME/XFCE.

## Custom User Setup
Edit `config/post_install.sh` to change the default username, password, or auto-login behaviors.
