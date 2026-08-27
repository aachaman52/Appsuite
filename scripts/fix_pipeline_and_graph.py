"""Fix graph package compatibility and pipeline internal imports."""
from pathlib import Path

# 1. src/pyflare/graph
flare_graph = Path("src/pyflare/graph")
flare_graph.mkdir(parents=True, exist_ok=True)
(flare_graph / "__init__.py").write_text(
    '"""Graph package forwarding to core orchestrator."""\n'
    'from ..core.orchestrator import GraphOrchestrator\n'
    'from ..core.job_state import JobState, WorkerStatus, WorkerResult\n',
    encoding="utf-8"
)
(flare_graph / "graph.py").write_text(
    '"""Graph orchestrator module."""\n'
    'from ..core.orchestrator import GraphOrchestrator\n',
    encoding="utf-8"
)
(flare_graph / "state.py").write_text(
    '"""Graph state module."""\n'
    'from ..core.job_state import JobState, WorkerStatus, WorkerResult\n',
    encoding="utf-8"
)

# 2. src/appsuite/graph
app_graph = Path("src/appsuite/graph")
app_graph.mkdir(parents=True, exist_ok=True)
(app_graph / "__init__.py").write_text(
    '"""Compatibility mirror for appsuite.graph -> pyflare.graph"""\n'
    'from pyflare.graph import *\n',
    encoding="utf-8"
)
(app_graph / "graph.py").write_text(
    '"""Compatibility mirror for appsuite.graph.graph"""\n'
    'from pyflare.graph.graph import *\n',
    encoding="utf-8"
)
(app_graph / "state.py").write_text(
    '"""Compatibility mirror for appsuite.graph.state"""\n'
    'from pyflare.graph.state import *\n',
    encoding="utf-8"
)

# 3. Fix pipeline/pipeline.py relative imports
pipeline_file = Path("src/pyflare/pipeline/pipeline.py")
content = pipeline_file.read_text(encoding="utf-8")
content = content.replace("from ..core.asset_normalizer import AssetNormalizer", "from .asset_normalizer import AssetNormalizer")
content = content.replace("from ..core.asset_registry import AssetRegistry", "from .asset_registry import AssetRegistry")
content = content.replace("from ..core.asset_router import AssetRouter", "from .asset_router import AssetRouter")
pipeline_file.write_text(content, encoding="utf-8")

print("Fixed pipeline and graph imports")
