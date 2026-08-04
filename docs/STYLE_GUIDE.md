# AppSuite Ecosystem — Style Guide

**Version:** 1.0.0 | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Documentation Style

- All documents use **GitHub Flavored Markdown**
- Every document includes: Title, Version, Status, Author, Last Updated header
- Tables of Contents required for documents over 500 lines
- Section headers: `##` for major, `###` for sub, `####` for detail
- Code blocks: always specify language (` ```python `, ` ```bash `, ` ```yaml `)
- Related Documents section at the end of every document

## Brand Voice

- Direct and technical — no marketing fluff
- Active voice preferred
- Acronyms defined on first use
- "PyFlare OS" (not "Pyflare OS" or "pyflare")
- "AppSuite Jarvis" (not "Jarvis" alone in formal docs)

## Visual Identity

- Primary font: Inter (UI), Space Grotesk (headings), JetBrains Mono (code)
- Dark theme default (`color-scheme: prefer-dark`)
- Accent colour: PyFlare flame orange-red (see `config/branding.yaml`)
- Logo: always use the SVG from `branding/logos/svg/pyflare.svg`

## Document Header Template

```markdown
# Title

**Version:** X.Y.Z | **Status:** Production/Draft/Deprecated | **Author:** Aachman Studios | **Last Updated:** YYYY-MM-DD
```

## Status Labels

| Label | Meaning |
|---|---|
| ✅ Complete | Implemented and tested |
| 🟡 In Progress | Partially implemented |
| 🔴 Planned | Not started |
| ⚠️ Deprecated | Being phased out |
| 🚫 Removed | No longer present |

---

## Related Documents

| Document | Purpose |
|---|---|
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code style |
| [CHANGELOG_GUIDE.md](CHANGELOG_GUIDE.md) | Changelog format |
