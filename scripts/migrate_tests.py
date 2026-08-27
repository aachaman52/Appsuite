"""Migrate and organize tests into unit, integration, and benchmarks directories."""
import shutil
from pathlib import Path

src_tests = Path("AppSuite_JarvisV1/tests")
tests_root = Path("tests")

unit_dir = tests_root / "unit"
integ_dir = tests_root / "integration"
bench_dir = tests_root / "benchmarks"

for d in [unit_dir, integ_dir, bench_dir]:
    d.mkdir(parents=True, exist_ok=True)

benchmarks = {
    "benchmark_adaptive_pipeline.py",
    "benchmark_fps.py",
    "test_graph_performance.py",
}

integrations = {
    "integration_e2e_pipeline.py",
    "real_pipeline_test.py",
    "stress_test.py",
    "test_memory_planning_integration.py",
    "test_project_improver_integration.py",
    "test_real_world_battle.py",
    "test_production_stress.py",
    "test_production_stress_hardening.py",
    "test_runtime_engine.py",
    "test_graph_orchestrator.py",
    "run_phase10_hardening.py",
    "failure_injection.py",
}

for test_file in src_tests.glob("*.py"):
    fname = test_file.name
    if fname in benchmarks:
        dest = bench_dir / fname
    elif fname in integrations:
        dest = integ_dir / fname
    else:
        dest = unit_dir / fname

    content = test_file.read_text(encoding="utf-8")
    
    # Update test_runtime_engine import error if present
    if fname == "test_runtime_engine.py":
        content = content.replace("from appsuite.core.state import RuntimeContext", "from pyflare.core.runtime_engine import RuntimeContext")
    
    dest.write_text(content, encoding="utf-8")
    print(f"Migrated {fname} -> {dest.parent.name}/{fname}")

print("Test suite migration complete")
