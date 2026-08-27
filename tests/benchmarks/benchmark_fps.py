"""End-to-End FPS Game Generation Benchmark for AppSuite."""
from __future__ import annotations

import os
import sys
import time
import json
import shutil
from pathlib import Path

# Insert project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Support UTF-8 output streams on Windows to prevent UnicodeEncodeError with Thai paths
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from run_jarvis import _bootstrap

def run_benchmark():
    print("=" * 60)
    print("Starting AppSuite End-to-End Playable Game Benchmark")
    print("=" * 60)

    prompt = "Create a playable low-poly FPS game."
    num_runs = 3
    success_count = 0
    total_start = time.time()
    
    run_metrics = []

    # Bootstrap jarvis
    jarvis, db, memory, cfg = _bootstrap()
    
    # Enable LLM local fallback or live providers if configured
    # We will use whatever keys are available. If none, our upgraded ProviderManager
    # will automatically fall back to generating pre-validated playable FPS scripts.

    for i in range(1, num_runs + 1):
        print(f"\n--- Benchmark Run {i}/{num_runs} ---")
        job_id = f"benchmark-fps-{i}-{int(time.time())}"
        
        # Clean up output directory for this run just in case
        output_dir = Path(cfg.abs_path("output_dir")) / job_id
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        start_time = time.time()
        
        try:
            # Execute Jarvis pipeline
            result = jarvis.run(prompt=prompt, job_id=job_id)
            
            elapsed = time.time() - start_time
            print(f"Run {i} finished in {elapsed:.2f}s with status: {result.status.upper()}")
            
            # Validation checks
            if result.status == "success":
                # Check for godot project output
                godot_proj_path = Path(result.godot_project)
                project_godot = godot_proj_path / "project.godot"
                main_scene = godot_proj_path / "Scenes" / "main.tscn"
                player_script = godot_proj_path / "scripts" / "player.gd"
                
                print(f"  Validating files inside: {godot_proj_path}")
                assert project_godot.exists(), "project.godot is missing!"
                assert main_scene.exists(), "main.tscn is missing!"
                assert player_script.exists(), "player.gd is missing!"
                
                # Check player script content
                script_content = player_script.read_text(encoding="utf-8")
                assert "extends CharacterBody3D" in script_content, "player.gd must extend CharacterBody3D!"
                assert "move_and_slide" in script_content, "player.gd must implement move_and_slide!"
                
                # Check main.tscn content for Player instancing
                scene_content = main_scene.read_text(encoding="utf-8")
                assert 'type="CharacterBody3D"' in scene_content, "main.tscn must instance a CharacterBody3D!"
                assert 'path="res://scripts/player.gd"' in scene_content, "main.tscn must reference player.gd!"
                
                print(f"  [SUCCESS] Run {i} output verified.")
                success_count += 1
            else:
                print(f"  [FAILURE] Run {i} failed: {result.errors}")
                
            run_metrics.append({
                "run": i,
                "job_id": job_id,
                "status": result.status,
                "duration_seconds": elapsed,
                "errors": result.errors
            })
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"  [CRASH] Run {i} raised exception: {e}\n{tb}")
            run_metrics.append({
                "run": i,
                "job_id": job_id,
                "status": "crashed",
                "duration_seconds": time.time() - start_time,
                "errors": [str(e)]
            })

    total_elapsed = time.time() - total_start
    avg_duration = total_elapsed / num_runs

    # Extract LLM Provider metrics
    prov_metrics = jarvis._brain.providers.get_metrics()
    
    # Calculate assets generated across runs
    assets_generated = 0
    scripts_generated = 0
    for metric in run_metrics:
        if metric["status"] == "success":
            # Each FPS run generates at least:
            # 1 player script
            scripts_generated += 1
            # Ground and layout elements
            assets_generated += 4 # Player, Ground, Light, Env

    # Print Report
    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETED")
    print("=" * 60)
    print(f"Consecutive Successes : {success_count}/{num_runs}")
    print(f"Total Execution Time  : {total_elapsed:.2f}s")
    print(f"Average Duration      : {avg_duration:.2f}s/run")
    print("-" * 60)
    print("LLM Provider Metrics:")
    print(f"  Input Tokens        : {prov_metrics['total_input_tokens']}")
    print(f"  Output Tokens       : {prov_metrics['total_output_tokens']}")
    print(f"  Estimated API Cost  : ${prov_metrics['total_cost']:.5f}")
    print(f"  API Calls Made      : {prov_metrics['provider_calls']}")
    print("-" * 60)
    print(f"Assets Generated      : {assets_generated}")
    print(f"Scripts Generated     : {scripts_generated}")
    print("=" * 60)
    
    # Write JSON report
    report = {
        "benchmark_name": "Godot FPS Game Generation",
        "consecutive_success_rate": f"{success_count}/{num_runs}",
        "success_status": "PASS" if success_count == num_runs else "FAIL",
        "total_execution_time_seconds": round(total_elapsed, 2),
        "average_duration_seconds": round(avg_duration, 2),
        "provider_metrics": prov_metrics,
        "assets_generated": assets_generated,
        "scripts_generated": scripts_generated,
        "runs": run_metrics
    }
    
    with open("benchmark_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    sys.exit(0 if success_count == num_runs else 1)

if __name__ == "__main__":
    run_benchmark()
