# PyFlare Repository Configuration & Security Settings

This document outlines recommended GitHub repository configurations, branch protection rules, and CI/CD security practices for **PyFlare**.

---

## 🛡️ Branch Protection Rules

Target Branch: `main`

### Recommended Settings:
1. **Require a pull request before merging:**
   - Require at least 1 approving review from code owners.
   - Dismiss stale pull request approvals when new commits are pushed.
   - Require review from Code Owners.
2. **Require status checks to pass before merging:**
   - Require branches to be up to date before merging.
   - Required status checks:
     - `Test Python 3.11 on ubuntu-latest`
     - `Test Python 3.12 on ubuntu-latest`
     - `Scan for committed secrets`
     - `Run Ruff Linter`
     - `Run Unit Tests with Coverage`
3. **Require signed commits** (Optional but recommended).
4. **Require linear history** (Allow squash merging or rebase merging).
5. **Do not allow bypassing the above settings** (Enforce for administrators).

---

## 🔒 Secret Scanning & Vulnerability Management

1. **GitHub Secret Scanning:** Enable secret scanning and push protection to automatically block commits containing API keys.
2. **Dependabot Alerts & Updates:** Enable Dependabot alerts and automated security updates for Python packages.
3. **Environment Secrets:** Store production and deployment credentials exclusively in GitHub Actions Repository Secrets, never in plain-text environment files.

---

## 📦 Packaging & Release Settings

- **Canonical Product Name:** `pyflare`
- **Supported Python Versions:** 3.11, 3.12 (3.13 supported once all third-party binary wheels confirm upstream parity).
- **Package Layout:** Standard `src/` layout (`src/pyflare/`).
- **CLI Entry Point:** `pyflare` -> `pyflare.cli:main`.
