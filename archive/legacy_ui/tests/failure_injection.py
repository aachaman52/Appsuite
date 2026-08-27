import os
import sys
import time
from pathlib import Path

# Ensure appsuite is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.main import AppContext
from appsuite.core.jarvis import JarvisCore
from appsuite.core.supervisor import Supervisor

def main():
    print("=== Failure Injection Test ===")
    
    from appsuite.config import load_config
    config = load_config()
    ctx = AppContext(config)
    jarvis = JarvisCore(ctx.config.scheduler, str(ctx.config.abs_path("output_dir")))
    
    supervisor = Supervisor(
        ctx.db, jarvis, ctx.pipeline, ctx.memory,
        scheduler_cfg=ctx.config.scheduler,
        retries_cfg=ctx.config.get("retries", {}),
        brain=ctx.brain
    )
    
    ctx.pipeline.supervisor = supervisor
    jarvis.wire(
        ctx.db, ctx.registry, ctx.memory, ctx.templates,
        ctx.pipeline.workers, ctx.pipeline, ctx.brain,
        ctx.hardware, ctx.token_banker
    )

    print("\n--- INJECTING: API Failure (Internet Worker Crash) ---")
    
    original_search = ctx.pipeline.workers["internet"].search_and_fetch
    def broken_search(*args, **kwargs):
        raise Exception("SIMULATED API TIMEOUT")
    
    ctx.pipeline.workers["internet"].search_and_fetch = broken_search
    res = jarvis.run("A medieval house")
    print(f"Result Status: {res.status}")
    if res.timeline:
        for t in res.timeline:
            print("  ", t)
            
    # Restore
    ctx.pipeline.workers["internet"].search_and_fetch = original_search

    print("\n--- INJECTING: Godot Binary Missing ---")
    original_godot = ctx.pipeline.workers["godot"]._binary_available
    ctx.pipeline.workers["godot"]._binary_available = lambda: False
    
    res2 = jarvis.run("An FPS map with crates and barrels")
    print(f"Result Status: {res2.status}")
    if res2.timeline:
        for t in res2.timeline:
            print("  ", t)
            
    ctx.pipeline.workers["godot"]._binary_available = original_godot
    
    print("\n--- INJECTING: Blender Texture Missing ---")
    # To simulate missing texture during blender validation, we'll patch the verifier
    original_verify = ctx.pipeline.workers["blender"]._verify_fbx_export
    from appsuite.workers.base import WorkerError
    def broken_verify(*args, **kwargs):
        raise WorkerError("TEXTURE_NOT_FOUND")
        
    ctx.pipeline.workers["blender"]._verify_fbx_export = broken_verify
    res3 = jarvis.run("A dense city street with modern cars")
    print(f"Result Status: {res3.status}")
    if res3.timeline:
        for t in res3.timeline:
            print("  ", t)
            
    ctx.pipeline.workers["blender"]._verify_fbx_export = original_verify
    
    print("\n=== All Injections Complete ===")

if __name__ == "__main__":
    main()
