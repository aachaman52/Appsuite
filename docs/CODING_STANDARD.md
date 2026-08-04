# AppSuite Ecosystem — Coding Standard

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## Python Standards

### Style

- **PEP 8** for all Python code
- **Type hints** required for all public functions and methods
- **Docstrings** required for all public classes and functions (Google style)
- Maximum line length: **100 characters**
- Use `from __future__ import annotations` in all modules for forward-reference support

### Imports

```python
# Standard library first
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party
from fastapi import FastAPI
import yaml

# Local (relative)
from .config import load_config
from ..db import Database
```

### Naming

| Element | Convention | Example |
|---|---|---|
| Module | snake_case | `jarvis_brain.py` |
| Class | PascalCase | `JarvisBrain` |
| Function/method | snake_case | `plan_execution()` |
| Constant | UPPER_SNAKE | `MAX_WORKERS` |
| Private | leading underscore | `_detect_cycles()` |
| File/config keys | snake_case | `default_config.yaml` |

### Dataclasses

Prefer `@dataclass` over plain dicts for structured data:

```python
@dataclass
class JarvisResult:
    job_id: str
    status: str   # "success" | "failed" | "partial"
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
```

### Logging

Use the project logger, not `print()`:

```python
from ..logging_setup import get_logger
log = get_logger("module.name")

log.info("Starting job %s", job_id[:8])
log.warning("Resource gate: %s", reason)
log.error("Pipeline failed: %s", exc)
```

### Error Handling

- Catch specific exceptions, not bare `except:`
- Always log exceptions with context before re-raising or suppressing
- Use `log.warning()` for recoverable errors, `log.error()` for failures

```python
try:
    result = worker.process(state)
except TimeoutError as exc:
    log.warning("[worker] Timeout after %ds: %s", timeout, exc)
    return WorkerResult(status=WorkerStatus.FAILED, reason="TASK_TIMEOUT")
except Exception as exc:
    log.error("[worker] Unexpected error: %s", exc, exc_info=True)
    raise
```

---

## YAML / JSON Standards

- 2-space indentation in YAML
- Comments explaining non-obvious fields
- All config files must have a header comment with the file's purpose
- Schema files must accompany all config JSON files

---

## Shell Script Standards

- `#!/bin/bash` shebang
- `set -e` (exit on error) at the top of all scripts
- Variables in `UPPER_SNAKE_CASE`
- Quote all variable expansions: `"$VARIABLE"`
- Descriptive `echo` output at each stage

---

## Documentation Standards

Every module must have:
- Module-level docstring explaining purpose and key classes
- Class docstring
- Method docstring for public methods

Every pull request must include:
- Updated documentation if interfaces change
- Updated `CHANGELOG.md` entry

---

## Related Documents

| Document | Purpose |
|---|---|
| [STYLE_GUIDE.md](STYLE_GUIDE.md) | Documentation style |
| [API_GUIDELINES.md](API_GUIDELINES.md) | API design |
| [TESTING.md](TESTING.md) | Test requirements |
