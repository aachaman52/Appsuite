# Contributing to PyFlare OS

## Getting Started

1. Fork the repository
2. Clone locally: `git clone https://github.com/aachman-studios/pyflare-os`
3. Install dependencies: `pip install -r requirements.txt`
4. Create a branch: `git checkout -b feature/my-feature`

## Areas to Contribute

| Area | Location | Skill Level |
|------|----------|-------------|
| Branding / design | `branding_generator/` | Intermediate |
| Desktop theme | `filesystem/usr/share/themes/` | Intermediate |
| App stubs | `applications/` | Beginner |
| Validation | `validation/` | Beginner |
| Build scripts | `scripts/` | Advanced |
| Documentation | `docs/` | Beginner |

## Standards

- Follow PEP 8 for Python
- Run `ruff check .` before committing
- Run `python validation/run_all.py` — all validators must pass
- Write tests for new validators

## Pull Request Checklist

- [ ] All validators pass
- [ ] Code is linted (ruff)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## Contact

Aachman Studios — hello@aachmanstudios.dev
