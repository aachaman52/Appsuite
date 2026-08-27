import time
import random
from pathlib import Path

from appsuite.db import Database
from appsuite.core.jarvis_memory import JarvisMemory
from appsuite.core.adaptive_scheduler import AdaptiveScheduler
from appsuite.core.state import WorkerResult, WorkerStatus

class DummyWorker:
    def __init__(self, name: str, base_fail_rate: float):
        self.name = name
        self.base_fail_rate = base_fail_rate
        
    def run(self, job, state):
        # Time cost
        time.sleep(random.uniform(0.01, 0.05))
        
        # Determine failure
        fail_rate = self.base_fail_rate
        
        # If blender, and assets > 1, fail more
        if self.name == "blender" and state.get("max_assets", 5) > 1:
            fail_rate += 0.4
            
        # If godot, and timeout < 100, fail more
        if self.name == "godot" and state.get("godot_timeout", 60) < 100:
            fail_rate += 0.3
            
        # Simulate network or random error
        if random.random() < fail_rate:
            return WorkerResult(status=WorkerStatus.FAILED, reason=f"{self.name} failed randomly")
            
        return WorkerResult(status=WorkerStatus.SUCCESS, data={})

class OldPipeline:
    def __init__(self, db, workers):
        self.db = db
        self.workers = workers
        
    def execute_job(self, job, state):
        sequence = ["internet", "analysis", "blender", "godot", "validation", "deploy"]
        start_time = time.time()
        success = True
        
        for w_name in sequence:
            worker = self.workers[w_name]
            w_start = time.time()
            res = worker.run(job, state)
            exec_time = time.time() - w_start
            
            is_ok = res.status == WorkerStatus.SUCCESS
            self.db.add_worker_execution(
                job_id=job["id"], worker_name=w_name, execution_time=exec_time,
                cpu_usage=50, ram_usage=500, gpu_usage=10,
                success=is_ok, retries=0, timeout=False, repair_triggered=False,
                tokens_used=100, assets_processed=state.get("max_assets", 5),
                failure_category=res.reason if not is_ok else ""
            )
            
            if not is_ok:
                success = False
                break
                
        return {"success": success, "time": time.time() - start_time}

def run_benchmark():
    db_path = Path("benchmark_adaptive.db")
    if db_path.exists():
        db_path.unlink()
        
    db = Database(db_path)
    memory = JarvisMemory(db)
    
    workers = {
        "internet": DummyWorker("internet", 0.05),
        "analysis": DummyWorker("analysis", 0.02),
        "blender": DummyWorker("blender", 0.1),
        "godot": DummyWorker("godot", 0.1),
        "validation": DummyWorker("validation", 0.01),
        "deploy": DummyWorker("deploy", 0.05)
    }
    
    # Pre-seed some failures for adaptive to learn
    for i in range(10):
        db.add_worker_execution("seed", "blender", 1.0, 50, 500, 10, False, 0, True, False, 100, 5, "timeout")
        db.add_worker_execution("seed", "godot", 1.0, 50, 500, 10, False, 0, True, False, 100, 5, "timeout")
    
    class DummyPipeline:
        def __init__(self, workers):
            self.workers = workers
            
    adaptive = AdaptiveScheduler(db, memory, DummyPipeline(workers))
    old_pipe = OldPipeline(db, workers)
    
    print("Running 100 jobs on OLD Pipeline...")
    old_successes = 0
    old_times = []
    
    for i in range(100):
        res = old_pipe.execute_job({"id": f"old_{i}"}, {"max_assets": 5, "godot_timeout": 60})
        if res["success"]:
            old_successes += 1
        old_times.append(res["time"])
        
    print(f"Old Pipeline - Success Rate: {old_successes}%")
    print(f"Old Pipeline - Avg Runtime: {sum(old_times)/100:.3f}s")
    
    print("\nRunning 100 jobs on ADAPTIVE Pipeline...")
    adapt_successes = 0
    adapt_times = []
    
    for i in range(100):
        res = adaptive.execute_job({"id": f"adapt_{i}"}, {"max_assets": 5, "godot_timeout": 60})
        # Check if all workers in sequence succeeded
        is_success = all(r.get("success", False) for r in res["results"].values())
        if is_success:
            adapt_successes += 1
        total_time = sum(r.get("time", 0) for r in res["results"].values())
        adapt_times.append(total_time)
        
    print(f"Adaptive Pipeline - Success Rate: {adapt_successes}%")
    print(f"Adaptive Pipeline - Avg Runtime: {sum(adapt_times)/100:.3f}s")
    
    # Generate Benchmark Report
    report = f"""# Adaptive Pipeline Benchmark Report
    
## Results
| Metric | Old Pipeline | Adaptive Pipeline |
|--------|-------------|-------------------|
| Success Rate | {old_successes}% | {adapt_successes}% |
| Avg Runtime | {sum(old_times)/100:.3f}s | {sum(adapt_times)/100:.3f}s |

## Optimization Decisions Triggered:
"""
    for dec in set(adaptive.optimization_decisions):
        report += f"- {dec}\n"
        
    report += "\n## Worker Statistics Tracker:\n"
    for w in workers.keys():
        stats = db.get_worker_stats(w)
        report += f"- **{w}**: Reliability {stats['reliability_score']:.2f}, Runs: {stats['total_runs']}, Failures: {stats['total_runs'] - int(stats['total_runs']*stats['success_rate'])}\n"
        
    Path("adaptive_benchmark_report.md").write_text(report)
    print("\nReport written to adaptive_benchmark_report.md")
    
    db.close()
    if db_path.exists():
        db_path.unlink()

if __name__ == "__main__":
    run_benchmark()
