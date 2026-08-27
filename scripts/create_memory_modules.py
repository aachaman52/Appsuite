"""Copy memory modules into memory and ensure imports are correct."""
import shutil
from pathlib import Path

core_dir = Path("src/pyflare/core")
mem_dir = Path("src/pyflare/memory")

for m in ["knowledge_graph.py", "jarvis_memory.py", "memory.py"]:
    src_f = Path("AppSuite_JarvisV1/appsuite/core") / m
    if src_f.exists():
        content = src_f.read_text(encoding="utf-8")
        content = content.replace("from ..db import Database", "from ..core.db import Database")
        content = content.replace("from .db import Database", "from ..core.db import Database")
        content = content.replace("from ..logging_setup import", "from ..core.logging_setup import")
        content = content.replace("from .logging_setup import", "from ..core.logging_setup import")
        (mem_dir / m).write_text(content, encoding="utf-8")
        print(f"Wrote memory/{m}")

print("Memory modules updated")
