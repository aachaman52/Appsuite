# AppSuite Ecosystem — Versioning

**Version:** 1.0.0 | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Semantic Versioning

Both PyFlare OS and AppSuite Jarvis use [Semantic Versioning 2.0.0](https://semver.org/).

**Format:** `MAJOR.MINOR.PATCH`

| Part | When incremented |
|---|---|
| MAJOR | Incompatible changes, new OS edition |
| MINOR | New features, backward-compatible |
| PATCH | Bug fixes only |

---

## PyFlare OS Codenames

Each major.minor release has a codename:

| Version | Codename | Status |
|---|---|---|
| 1.0.0 | **Ember** | ✅ Current |
| 1.1.0 | **Flare** | 🔴 Planned |
| 1.2.0 | **Nova** | 🔴 Planned |
| 2.0.0 | **Ignite** | 🔴 Planned |

Codenames are defined in `config/branding.yaml`:
```yaml
product:
  codename: "Ember"
  series: "1.x"
```

---

## ISO Filename Convention

```
pyflare-os-{version}-{codename}-{arch}.iso
pyflare-os-1.0.0-ember-amd64.iso
```

---

## AppSuite Jarvis Versioning

Jarvis version is tracked in `appsuite/__init__.py`:
```python
__version__ = "1.0.0"
```

Exposed via the FastAPI root endpoint:
```json
{"app": "AppSuite", "version": "1.0.0", "docs": "/docs"}
```

---

## Related Documents

| Document | Purpose |
|---|---|
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | Release workflow |
| [CHANGELOG_GUIDE.md](CHANGELOG_GUIDE.md) | Changelog format |
| [MILESTONES.md](MILESTONES.md) | Release roadmap |
