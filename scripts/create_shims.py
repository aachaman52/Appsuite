"""Helper script to create compatibility shims."""
from pathlib import Path

appsuite_dir = Path("src/appsuite")
appsuite_dir.mkdir(parents=True, exist_ok=True)

(appsuite_dir / "__init__.py").write_text(
    '"""Compatibility layer mapping appsuite -> pyflare."""\n'
    'from pyflare import *\n'
    'from pyflare import __version__, __product__\n',
    encoding="utf-8"
)

for f in ["config", "db", "logging_setup", "main", "models"]:
    (appsuite_dir / f"{f}.py").write_text(
        f'"""Compatibility module for appsuite.{f} -> pyflare.core.{f}"""\n'
        f'from pyflare.core.{f} import *\n',
        encoding="utf-8"
    )

subpackages = {
    "agents": "agents",
    "api": "api",
    "workers": "workers",
    "pipeline": "pipeline",
    "plugins": "plugins",
    "engine": "core",
    "utils": "pipeline",
    "core": "core",
}

for sub, target in subpackages.items():
    sdir = appsuite_dir / sub
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "__init__.py").write_text(
        f'"""Compatibility package for appsuite.{sub} -> pyflare.{target}"""\n'
        f'from pyflare.{target} import *\n',
        encoding="utf-8"
    )

# Submodules inside core
core_dir = appsuite_dir / "core"
(core_dir / "semantic_memory").mkdir(parents=True, exist_ok=True)
(core_dir / "semantic_memory" / "__init__.py").write_text(
    '"""Compatibility for appsuite.core.semantic_memory"""\n'
    'from pyflare.memory import *\n',
    encoding="utf-8"
)

# All files in pyflare/core should also be importable as appsuite.core.<file>
for pyf in Path("src/pyflare/core").glob("*.py"):
    if pyf.name != "__init__.py":
        (core_dir / pyf.name).write_text(
            f'"""Compatibility for appsuite.core.{pyf.stem}"""\n'
            f'from pyflare.core.{pyf.stem} import *\n',
            encoding="utf-8"
        )

# Modules moved to other packages
for s_name in ["adaptive_scheduler", "background_scheduler", "worker_scorer"]:
    (core_dir / f"{s_name}.py").write_text(
        f'"""Compatibility for appsuite.core.{s_name}"""\n'
        f'from pyflare.scheduler.{s_name} import *\n',
        encoding="utf-8"
    )

for p_name in ["asset_normalizer", "asset_registry", "asset_router"]:
    (core_dir / f"{p_name}.py").write_text(
        f'"""Compatibility for appsuite.core.{p_name}"""\n'
        f'from pyflare.pipeline.{p_name} import *\n',
        encoding="utf-8"
    )

for m_name in ["knowledge_graph", "jarvis_memory", "memory"]:
    (core_dir / f"{m_name}.py").write_text(
        f'"""Compatibility for appsuite.core.{m_name}"""\n'
        f'from pyflare.memory.{m_name} import *\n',
        encoding="utf-8"
    )

(core_dir / "provider_manager.py").write_text(
    '"""Compatibility for appsuite.core.provider_manager"""\n'
    'from pyflare.providers.provider_manager import *\n',
    encoding="utf-8"
)

(appsuite_dir / "utils" / "gltf_converter.py").write_text(
    '"""Compatibility for appsuite.utils.gltf_converter"""\n'
    'from pyflare.pipeline.gltf_converter import *\n',
    encoding="utf-8"
)

print("Compatibility layer created in src/appsuite")
