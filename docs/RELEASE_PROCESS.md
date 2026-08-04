# AppSuite Ecosystem — Release Process

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Release Types

| Type | Trigger | Example |
|---|---|---|
| **Major** | Breaking changes, new OS codename | v1.0.0 → v2.0.0 |
| **Minor** | New features, new applications | v1.0.0 → v1.1.0 |
| **Patch** | Bug fixes, security patches | v1.0.0 → v1.0.1 |

---

## PyFlare OS Release Process

### Pre-Release Checklist

```
[ ] Version bumped in config/branding.yaml
[ ] Version bumped in config/default.yaml
[ ] CHANGELOG.md updated with release notes
[ ] All validators passing: python validation/run_all.py
[ ] Branding assets regenerated and validated
[ ] Full ISO build completed and booted
[ ] Hardware test completed (bare metal or VM)
[ ] Release branch created: git checkout -b release/v1.x.x
```

### Build

```bash
# On Linux build host
python -m branding_generator.main generate
python -m branding_generator.main validate
python validation/run_all.py
sudo python3 build.py --config config/default.yaml
python scripts/generate_checksums.py
```

### Artefacts

| Artefact | Description |
|---|---|
| `pyflare-os-{version}-{codename}-amd64.iso` | Bootable hybrid ISO |
| `pyflare-os-{version}-{codename}-amd64.iso.sha256` | SHA256 checksum |
| `pyflare-os-{version}-{codename}-amd64.iso.md5` | MD5 checksum |
| `manifest.json` | Build manifest (packages, timestamps) |

### GitHub Release

1. Tag: `git tag -a v1.0.0 -m "PyFlare OS 1.0.0 Ember"`
2. Push tag: `git push origin v1.0.0`
3. Create GitHub Release with changelog notes
4. Attach ISO and checksums as release artefacts

---

## AppSuite Jarvis Release Process

### Pre-Release Checklist

```
[ ] Version bumped in appsuite/__init__.py
[ ] CHANGELOG.md updated
[ ] All tests passing: pytest tests/ -v
[ ] Benchmark report generated
[ ] requirements.txt pinned to tested versions
```

### Versioning

Jarvis version is independent from PyFlare OS. It follows semantic versioning tied to the phase roadmap:
- Phase 1–11 completions are v1.x releases
- Phase 12+ (cloud) will be v2.x

---

## Versioning Strategy

See [VERSIONING.md](VERSIONING.md) for the full versioning policy.

### Current Versions

| Component | Version |
|---|---|
| PyFlare OS | 1.0.0 (Ember) |
| AppSuite Jarvis | 1.0.0 |
| LangGraph (vendored) | See `langgraph-main/libs/langgraph/pyproject.toml` |

---

## Related Documents

| Document | Purpose |
|---|---|
| [VERSIONING.md](VERSIONING.md) | Version numbering |
| [CHANGELOG_GUIDE.md](CHANGELOG_GUIDE.md) | Changelog format |
| [TESTING.md](TESTING.md) | Test requirements |
| [BUILD_PIPELINE.md](BUILD_PIPELINE.md) | Build system |
