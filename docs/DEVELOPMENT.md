# AppSuite Ecosystem — Development Guide

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Table of Contents

1. [Repository Setup](#repository-setup)
2. [PyFlare OS Development](#pyflare-os-development)
3. [AppSuite Jarvis Development](#appsuite-jarvis-development)
4. [Running Tests](#running-tests)
5. [VS Code Setup](#vs-code-setup)
6. [Git Workflow](#git-workflow)
7. [Related Documents](#related-documents)

---

## Repository Setup

```bash
git clone https://github.com/aachaman52/Appsuite.git
cd Appsuite
```

The repository contains three sub-projects with separate virtual environments.

---

## PyFlare OS Development

### Setup (Windows/Linux/macOS)

```bash
cd PyFlare
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Branding Workflow

```bash
# Edit brand tokens
# Edit: config/branding.yaml  (product name, version, URLs)
# Edit: branding_generator/config.py  (colours, font sizes)

# Regenerate all assets
python -m branding_generator.main generate

# Validate output
python -m branding_generator.main validate

# View validation report
cat branding/validation_report.json
```

### Validation Workflow

```bash
# Run all 14 validators
python validation/run_all.py

# Run a specific validator
python validation/validate_branding.py
python validation/validate_filesystem.py
python validation/validate_configs.py
```

### ISO Build (Linux only)

```bash
# Install system dependencies
sudo bash scripts/install_dependencies.sh

# Full build
sudo python3 build.py --config config/default.yaml

# Clean build artefacts
python scripts/clean.py
```

---

## AppSuite Jarvis Development

### Setup

```bash
cd AppSuite_JarvisV1

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Environment Variables

Create `.env` in `AppSuite_JarvisV1/`:

```env
# Required for LLM features (at least one)
NVIDIA_API_KEY=nvapi-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: local Ollama
# OLLAMA_BASE_URL=http://localhost:11434

# Database
DB_PATH=data/appsuite.db

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs/
```

### Starting the Server

```bash
# Development server (auto-reload)
uvicorn appsuite.main:app --reload --port 8000

# Or via the module entry point
python -m appsuite

# Or via the run script
python run_jarvis.py
```

API docs available at: `http://localhost:8000/docs`

### Running a Job

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/jobs \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Create a medieval village scene"}'

# Via run_job.py script
python scripts/run_job.py --prompt "Create a medieval village"
```

### Database Initialisation

```bash
python scripts/init_db.py
```

This creates all SQLite tables in `data/appsuite.db`.

---

## Running Tests

### PyFlare OS Tests

```bash
cd PyFlare

# All validators
python validation/run_all.py

# pytest suite
pytest tests/ -v
```

### AppSuite Jarvis Tests

```bash
cd AppSuite_JarvisV1

# All tests
pytest tests/ -v

# Pipeline reliability tests
python scripts/test_pipeline_reliability.py

# Godot integration
python scripts/test_godot_integration.py

# Real asset tests
python scripts/test_real_assets.py

# Generate benchmark report
python scripts/generate_benchmark_report.py
```

---

## VS Code Setup

The workspace `.vscode/settings.json` contains:

```json
{
    "git.ignoreLimitWarning": true
}
```

Recommended extensions:
- **Python** (ms-python.python)
- **Pylance** (ms-python.vscode-pylance)
- **Ruff** (charliermarsh.ruff) — linting
- **YAML** (redhat.vscode-yaml)
- **Markdown All in One**

Recommended workspace settings (add to `.vscode/settings.json`):

```json
{
    "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
    "editor.formatOnSave": true,
    "python.formatting.provider": "ruff",
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

---

## Git Workflow

### Branch Strategy

```
main          Production-ready code
├── dev       Integration branch
├── feature/* Feature branches
├── fix/*     Bug fix branches
└── docs/*    Documentation branches
```

### Commit Convention

```
type(scope): description

Types: feat, fix, docs, style, refactor, test, chore, build
Scope: pyflare, jarvis, branding, engine, agents, workers, docs

Examples:
feat(branding): add animated favicon generation
fix(engine): resolve deadlock in GraphOrchestrator when all tasks fail
docs(jarvis): add AI_ARCHITECTURE.md
build(pyflare): add xorriso UEFI hybrid flag
```

### Pre-Commit Checklist

Before pushing:

```bash
# PyFlare
python validation/run_all.py
pytest tests/ -v

# Jarvis
pytest tests/ -v

# No large binary files
git status  # check nothing >50MB is staged
```

---

## Related Documents

| Document | Purpose |
|---|---|
| [CODING_STANDARD.md](CODING_STANDARD.md) | Code style rules |
| [TESTING.md](TESTING.md) | Test suite reference |
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | How releases are made |
| [API_GUIDELINES.md](API_GUIDELINES.md) | FastAPI endpoint design |
