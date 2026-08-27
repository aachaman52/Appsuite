"""Create forwarding modules in src/pyflare/core."""
from pathlib import Path

core_dir = Path("src/pyflare/core")

# Semantic memory
(core_dir / "semantic_memory.py").write_text(
    '"""Forwarding module for memory.semantic_memory."""\n'
    'from pyflare.memory.semantic_memory import *\n'
    'from pyflare.memory import SemanticMemory\n',
    encoding="utf-8"
)

(core_dir / "jarvis_memory.py").write_text(
    '"""Forwarding module for memory.jarvis_memory."""\n'
    'from pyflare.memory.jarvis_memory import *\n',
    encoding="utf-8"
)

(core_dir / "knowledge_graph.py").write_text(
    '"""Forwarding module for memory.knowledge_graph."""\n'
    'from pyflare.memory.knowledge_graph import *\n',
    encoding="utf-8"
)

# Providers
(core_dir / "provider_manager.py").write_text(
    '"""Forwarding module for providers.provider_manager."""\n'
    'from pyflare.providers.provider_manager import *\n',
    encoding="utf-8"
)

# Scheduler
for s in ["adaptive_scheduler", "background_scheduler", "worker_scorer"]:
    (core_dir / f"{s}.py").write_text(
        f'"""Forwarding module for scheduler.{s}."""\n'
        f'from pyflare.scheduler.{s} import *\n',
        encoding="utf-8"
    )

# Pipeline
for p in ["asset_normalizer", "asset_registry", "asset_router"]:
    (core_dir / f"{p}.py").write_text(
        f'"""Forwarding module for pipeline.{p}."""\n'
        f'from pyflare.pipeline.{p} import *\n',
        encoding="utf-8"
    )

# Plugins
(core_dir / "plugin_manager.py").write_text(
    '"""Forwarding module for plugins.plugin_manager."""\n'
    'from pyflare.plugins.plugin_manager import *\n',
    encoding="utf-8"
)

print("Forwarding modules successfully created in core/")
