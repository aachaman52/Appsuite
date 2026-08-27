import os
import sys
import time
import random
from pathlib import Path

# Ensure appsuite is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.main import AppContext
from appsuite.core.jarvis import JarvisCore
from appsuite.core.supervisor import Supervisor

def main():
    print("=== Production Stress Test (20 Jobs) ===")
    
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
    
    base_prompts = [
        "A low poly medieval cart",
        "Sci-fi corridor segment",
        "A collection of fantasy weapons",
        "Office furniture pack",
        "A ruined wall section",
        "Cyberpunk street sign",
        "A grassy hill terrain",
        "Food props for a market stall",
        "A small wooden boat",
        "Industrial pipes and valves"
    ]
    
    metrics = {
        "success": 0,
        "failed": 0,
        "total_time": 0.0,
        "cache_hits": 0,
        "failures": []
    }
    
    NUM_JOBS = 20
    
    # We will just pick from base_prompts randomly so there are likely memory cache hits
    for i in range(NUM_JOBS):
        prompt = random.choice(base_prompts)
        print(f"\n[{i+1}/{NUM_JOBS}] Executing: {prompt}")
        
        t0 = time.time()
        res = jarvis.run(prompt)
        dt = time.time() - t0
        
        metrics["total_time"] += dt
        
        if res.status == "success":
            metrics["success"] += 1
            if res.plan.use_cached_assets:
                metrics["cache_hits"] += 1
        else:
            metrics["failed"] += 1
            metrics["failures"].extend(res.errors)
            
        time.sleep(1) # buffer
        
    avg_time = metrics["total_time"] / NUM_JOBS
    
    print("\n" + "="*40)
    print("        STRESS TEST REPORT")
    print("="*40)
    print(f"Total Jobs : {NUM_JOBS}")
    print(f"Success    : {metrics['success']}")
    print(f"Failed     : {metrics['failed']}")
    print(f"Success %  : {(metrics['success']/NUM_JOBS)*100:.1f}%")
    print(f"Avg Time   : {avg_time:.2f}s")
    print(f"Cache Hits : {metrics['cache_hits']}")
    print("Errors Encountered:")
    for err in set(metrics["failures"]):
        print(f" - {err}")
        
if __name__ == "__main__":
    main()
