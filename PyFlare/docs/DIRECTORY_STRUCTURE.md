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
