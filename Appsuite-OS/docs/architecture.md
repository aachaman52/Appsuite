# Architecture

AppSuite OS is a derivative of Ubuntu 24.04 LTS built via remastering. It operates on a robust layer architecture:

1. **Base Kernel & GNU/Linux Userland**: Provided entirely upstream by Ubuntu/Debian. No custom compilation of the kernel minimizes security and maintenance overhead.
2. **AppSuite Configuration Layer**: Injected via chroot (`config/packages.yaml` and `config/post_install.sh`). This installs all essential graphics drivers (NVIDIA 535+), media engines (FFmpeg), and game engines (Godot/Blender) pre-compiled, skipping the need for an internet connection during a live session.
3. **AppSuite Branding Layer**: Handled through Plymouth boot splash overrides, custom GRUB backgrounds, and GTK theme injection.

## Why Ubuntu LTS?
Ubuntu LTS provides a 5-year hardware enablement stack (HWE), ensuring compatibility with high-end NVIDIA graphics cards needed for AppSuite's AI vision models and Blender rendering tasks, while keeping the dependency graph stable.
