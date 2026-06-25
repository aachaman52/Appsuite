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
    print("=== Real Pipeline Test ===")
    
    # Initialize context and wire Jarvis
    from appsuite.config import load_config
    config = load_config()
    ctx = AppContext(config)
    jarvis = JarvisCore(ctx.config.scheduler, str(ctx.config.abs_path("output_dir")))
    
    # Initialize Supervisor
    supervisor = Supervisor(
        ctx.db,
        jarvis,
        ctx.pipeline,
        ctx.memory,
        scheduler_cfg=ctx.config.scheduler,
        retries_cfg=ctx.config.get("retries", {}),
        brain=ctx.brain
    )
    
    # Wire Supervisor into pipeline
    ctx.pipeline.supervisor = supervisor
    
    # Wire Jarvis
    jarvis.wire(
        ctx.db, ctx.registry, ctx.memory, ctx.templates,
        ctx.pipeline.workers, ctx.pipeline, ctx.brain,
        ctx.hardware, ctx.token_banker
    )
    
    prompts = [
        "A small medieval house scene",
        "An FPS map with crates and barrels",
        "A dense city street with modern cars",
        "A random assortment of low poly props"
    ]
    
    results = []
    
    for prompt in prompts:
        print(f"\n>> Running Prompt: {prompt}")
        res = jarvis.run(prompt)
        results.append(res)
        time.sleep(2)  # small buffer
        
    print("\n=== Final Test Summary ===")
    for r in results:
        print(f"[{r.job_id[:8]}] {r.status.upper()} ({r.duration_seconds:.1f}s) - {r.prompt}")
        print(f"   Assets: {r.asset_count} fetched")
        if r.status == "success":
            print(f"   Deployment: {r.deployment_url}")
            
if __name__ == "__main__":
    main()
