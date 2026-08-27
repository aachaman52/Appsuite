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
