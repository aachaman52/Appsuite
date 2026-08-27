import os
import shutil
import time
from pathlib import Path

from appsuite.db import Database
from appsuite.core.runtime_engine import RuntimeExecutionEngine, EventBus, DynamicDAG
from appsuite.core.jarvis_memory import JarvisMemory
from appsuite.config import load_config
from appsuite.workers.internet_worker import InternetWorker
from appsuite.workers.analysis_worker import AnalysisWorker
from appsuite.workers.blender_worker import BlenderWorker
from appsuite.workers.godot_worker import GodotWorker
from appsuite.workers.code_worker import CodeWorker
from appsuite.workers.validation_worker import ValidationWorker
from appsuite.workers.deploy_worker import DeployWorker
from appsuite.core.strategy_analyzer import StrategyAnalyzer

def setup_pipeline():
    cfg = load_config()
    db_path = cfg.abs_path("database_path")
    if db_path.exists():
        db_path.unlink() # Fresh DB for E2E
        
    db = Database(db_path)
    memory = JarvisMemory(db)
    bus = EventBus()
    
    # Track events to print
    def on_event(event, data):
        print(f"[{time.strftime('%H:%M:%S')}] {event}: {data.get('worker', '')} {data.get('job_id', '')}")
    bus.subscribe("*", on_event)
    
    # Load all real workers
    worker_classes = [
        InternetWorker,
        AnalysisWorker,
        BlenderWorker,
        GodotWorker,
        CodeWorker,
        ValidationWorker,
        DeployWorker
    ]
    workers = {}
    
    # Providers for Code & Analysis (stubbed to local fallback if no API keys)
    from appsuite.core.provider_manager import ProviderManager
    providers = ProviderManager(cfg.providers)
    
    # Fake registry for internet worker
    from appsuite.core.asset_registry import AssetRegistry
    registry = AssetRegistry(db)
    
    # Initialize workers with real config
    for WClass in worker_classes:
        name = WClass.name
        if name == "internet":
            w = WClass(
                cfg.raw.get("workers", {}).get(name, {}),
                {}, {},
                provider_manager=providers,
                registry=registry,
                assets_dir=cfg.abs_path("assets_dir"),
                cache_dir=cfg.abs_path("cache_dir")
            )
        elif name == "code":
            w = WClass(
                cfg.raw.get("workers", {}).get(name, {}),
                {}, {},
                provider_manager=providers
            )
        elif name in ("blender", "godot", "deploy"):
            w = WClass(
                cfg.raw.get("workers", {}).get(name, {}),
                {}, {},
                output_dir=cfg.abs_path("output_dir")
            )
        else:
            w = WClass(
                cfg.raw.get("workers", {}).get(name, {}),
                {}, {}
            )
        workers[name] = w
        
    # Ensure project improver exists
    from appsuite.core.project_improver import ProjectImprover
    workers["improver"] = ProjectImprover(db=db, memory=memory)
        
    engine = RuntimeExecutionEngine(db, workers, bus)
    return engine, db, memory

def run_e2e():
    print("Starting AppSuite V1 End-to-End Real Pipeline Integration Test\n")
    print("WARNING: This requires internet access and Godot/Blender installed in config.")
    
    engine, db, memory = setup_pipeline()
    
    prompts = [
        "A playable FPS game with a gun, enemies, and a city level.",
        "A 3D Platformer game with coins and jumping mechanics in a forest.",
        "A Top-down Shooter in a space station.",
        "A 3D Puzzle game with interactive blocks.",
        "An Open World Prototype with roads, houses, and trees."
    ]
    
    sequence = ["internet", "analysis", "blender", "godot", "code", "validation", "deploy"]
    
    for i, prompt in enumerate(prompts):
        job_id = f"e2e_job_{i}"
        print(f"\n========================================================")
        print(f" GENERATING: {prompt}")
        print(f"========================================================")
        
        job = {
            "id": job_id,
            "prompt": prompt,
            "status": "running",
            "template": {
                "asset_slots": [
                    {"role": "player", "search_terms": ["character", "player"], "count": 1},
                    {"role": "environment", "search_terms": ["ground", "level"], "count": 1}
                ]
            }
        }
        
        # We start with the full real sequence. 
        # The engine will dynamically insert the improver if validation fails.
        ctx = engine.execute(job, sequence.copy())
        
        if ctx.current_state.name == "COMPLETED":
            print(f"\n[SUCCESS] Generated playable game for: {prompt}")
        else:
            print(f"\n[FAILED] Pipeline failed for: {prompt}")
            if ctx.current_errors:
                print(f"Errors: {ctx.current_errors[-1]}")
                
        print(f"Execution time: {ctx.execution_time:.2f}s")
        print(f"Workers executed: {ctx.workers_finished}")
        
    print("\nE2E Integration Testing Finished.")
    
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.generate_benchmark_report import generate_report
    generate_report()

if __name__ == "__main__":
    run_e2e()
