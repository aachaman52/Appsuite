# Security Policy — PyFlare OS

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email: security@aachmanstudios.dev

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 72 hours and aim to patch within 14 days.

## Security Principles

- No telemetry by default
- No cloud accounts required
- SSH hardened (no root login, modern ciphers only)
- sysctl hardened (kernel pointer restriction, dmesg restriction)
- UFW firewall enabled
- AppArmor enabled (Ubuntu default)
