"""Create semantic_memory compatibility directory inside core."""
import os
from pathlib import Path

core_dir = Path("src/pyflare/core")
file_sem = core_dir / "semantic_memory.py"
if file_sem.exists():
    file_sem.unlink()

dir_sem = core_dir / "semantic_memory"
dir_sem.mkdir(parents=True, exist_ok=True)

(dir_sem / "__init__.py").write_text(
    '"""Compatibility package for core.semantic_memory -> memory."""\n'
    'from pyflare.memory import *\n'
    'from pyflare.memory.semantic_memory import *\n',
    encoding="utf-8"
)

for m in ["embedding_client", "strategy_memory", "failure_memory", "procedural_memory", "agent_memory", "worker_memory"]:
    (dir_sem / f"{m}.py").write_text(
        f'"""Compatibility module for core.semantic_memory.{m} -> memory.{m}."""\n'
        f'from pyflare.memory.{m} import *\n',
        encoding="utf-8"
    )

print("Created core/semantic_memory compatibility package")
