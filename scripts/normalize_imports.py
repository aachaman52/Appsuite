"""Audit and normalize imports across all src/pyflare submodules."""
import re
from pathlib import Path

pyflare_dir = Path("src/pyflare")

replacements = [
    # In providers/
    ("src/pyflare/providers", r"from \.token_banker import TokenBanker", "from ..core.token_banker import TokenBanker"),
    ("src/pyflare/providers", r"from \.db import", "from ..core.db import"),
    
    # In scheduler/
    ("src/pyflare/scheduler", r"from \.token_banker import", "from ..core.token_banker import"),
    ("src/pyflare/scheduler", r"from \.db import", "from ..core.db import"),
    ("src/pyflare/scheduler", r"from \.models import", "from ..core.models import"),
    ("src/pyflare/scheduler", r"from \.logging_setup import", "from ..core.logging_setup import"),

    # In pipeline/
    ("src/pyflare/pipeline", r"from \.token_banker import", "from ..core.token_banker import"),
    ("src/pyflare/pipeline", r"from \.db import", "from ..core.db import"),
    ("src/pyflare/pipeline", r"from \.models import", "from ..core.models import"),
    ("src/pyflare/pipeline", r"from \.logging_setup import", "from ..core.logging_setup import"),
    ("src/pyflare/pipeline", r"from \.state import", "from ..core.state import"),

    # In memory/
    ("src/pyflare/memory", r"from \.token_banker import", "from ..core.token_banker import"),
    ("src/pyflare/memory", r"from \.db import", "from ..core.db import"),
    ("src/pyflare/memory", r"from \.models import", "from ..core.models import"),
    ("src/pyflare/memory", r"from \.logging_setup import", "from ..core.logging_setup import"),
    ("src/pyflare/memory", r"from \.provider_manager import", "from ..providers.provider_manager import"),

    # In workers/
    ("src/pyflare/workers", r"from \.state import", "from ..core.state import"),
    ("src/pyflare/workers", r"from \.models import", "from ..core.models import"),
    ("src/pyflare/workers", r"from \.db import", "from ..core.db import"),
]

for folder, pattern, repl in replacements:
    p = Path(folder)
    if p.exists():
        for pyfile in p.glob("*.py"):
            content = pyfile.read_text(encoding="utf-8")
            new_content = re.sub(pattern, repl, content)
            if new_content != content:
                pyfile.write_text(new_content, encoding="utf-8")
                print(f"Updated {folder}/{pyfile.name}: {pattern} -> {repl}")

print("Normalized submodule imports")
