# AppSuite Ecosystem — Networking

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## PyFlare OS Networking

### Installed Packages

| Package | Purpose |
|---|---|
| `network-manager` | Connection manager daemon |
| `network-manager-gnome` | GNOME control panel integration |
| `network-manager-openvpn` | OpenVPN backend |
| `wireless-tools` | Wi-Fi configuration utilities |
| `wpasupplicant` | WPA/WPA2 authentication |
| `openssh-client` | SSH client |
| `openssh-server` | SSH server (installed, disabled by default) |
| `nftables` | Kernel firewall (modern iptables replacement) |
| `ufw` | Uncomplicated Firewall frontend |
| `avahi-daemon` | mDNS/DNS-SD for local network discovery |
| `curl` / `wget` | HTTP clients |

### Default Network Configuration

- **Wired**: DHCP by default via NetworkManager
- **Wi-Fi**: NetworkManager with WPA2/WPA3 support
- **Firewall**: UFW active, default deny-incoming
- **mDNS**: Avahi enabled for `.local` hostname resolution
- **DNS**: `systemd-resolved` for DNS caching

### Ollama Network

Ollama binds to `localhost:11434`. It is not accessible remotely by default. To enable remote access:

```bash
OLLAMA_HOST=0.0.0.0:11434 systemctl restart ollama
# Also open UFW: sudo ufw allow 11434
```

---

## AppSuite Jarvis Networking

### FastAPI Server

The Jarvis server binds to `0.0.0.0:8000` by default. CORS is configured to allow all origins (development mode). For production, restrict CORS origins.

### Provider API Calls

Jarvis makes outbound HTTPS calls to:

| Provider | Endpoint |
|---|---|
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta` |
| Anthropic | `https://api.anthropic.com/v1` |
| Poly Haven | `https://api.polyhaven.com` |
| Sketchfab | `https://api.sketchfab.com` (via plugin) |

All calls are made with standard HTTPS. API keys are passed as Bearer tokens in Authorization headers.

### Asset Downloads

`InternetWorker` downloads 3D assets (GLB, FBX, OBJ, ZIP) from Poly Haven CDN. Downloads are cached in `cache/` to avoid repeated fetches.

---

## Related Documents

| Document | Purpose |
|---|---|
| [SECURITY.md](SECURITY.md) | Security model |
| [PACKAGE_SYSTEM.md](PACKAGE_SYSTEM.md) | Installed packages |
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | Provider manager |
