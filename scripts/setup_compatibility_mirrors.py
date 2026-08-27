"""Setup complete compatibility mirrors and fix internal engine references."""
import re
from pathlib import Path

# 1. Create src/pyflare/engine forwarding package
engine_dir = Path("src/pyflare/engine")
engine_dir.mkdir(parents=True, exist_ok=True)
for mod in ["job_state", "worker_protocol", "checkpoint", "observability", "orchestrator", "langgraph_agent", "event_bus"]:
    (engine_dir / f"{mod}.py").write_text(
        f'"""Forwarding for engine.{mod} -> core.{mod}"""\n'
        f'from ..core.{mod} import *\n',
        encoding="utf-8"
    )
(engine_dir / "__init__.py").write_text(
    '"""Engine compatibility package."""\n'
    'from ..core.job_state import *\n'
    'from ..core.worker_protocol import *\n',
    encoding="utf-8"
)

# 2. Fix engine imports in pyflare
for pyfile in Path("src/pyflare").rglob("*.py"):
    content = pyfile.read_text(encoding="utf-8")
    new_content = re.sub(r'from \.\.engine\.(job_state|worker_protocol|checkpoint|observability|orchestrator)\b', r'from ..core.\1', content)
    if new_content != content:
        pyfile.write_text(new_content, encoding="utf-8")
        print(f"Fixed engine import in {pyfile.relative_to('src/pyflare')}")

# 3. Populate all submodules in src/appsuite
appsuite_dir = Path("src/appsuite")
appsuite_dir.mkdir(parents=True, exist_ok=True)

for sub in ["agents", "api", "workers", "pipeline", "plugins", "providers", "scheduler", "core", "memory", "engine"]:
    s_dst = appsuite_dir / sub
    s_dst.mkdir(parents=True, exist_ok=True)
    src_sub = Path("src/pyflare") / (sub if sub != "engine" else "core")
    if src_sub.exists():
        for f in src_sub.glob("*.py"):
            target_pkg = "core" if sub == "engine" else sub
            (s_dst / f.name).write_text(
                f'"""Compatibility mirror for appsuite.{sub}.{f.stem} -> pyflare.{target_pkg}.{f.stem}"""\n'
                f'from pyflare.{target_pkg}.{f.stem} import *\n',
                encoding="utf-8"
            )

# Ensure appsuite.core.semantic_memory has all submodules
sem_dst = appsuite_dir / "core" / "semantic_memory"
sem_dst.mkdir(parents=True, exist_ok=True)
for f in Path("src/pyflare/memory").glob("*.py"):
    (sem_dst / f.name).write_text(
        f'"""Compatibility mirror for appsuite.core.semantic_memory.{f.stem} -> pyflare.memory.{f.stem}"""\n'
        f'from pyflare.memory.{f.stem} import *\n',
        encoding="utf-8"
    )

print("Compatibility mirrors and engine package created successfully")
