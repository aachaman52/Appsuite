"""Observability and Metrics dashboard generator."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

class MetricsGenerator:
    def __init__(self, db: Any):
        self.db = db

    def generate_metrics_report(self, output_path: Path) -> None:
        """
        Aggregates data from SQLite and exports execution_metrics.json
        """
        try:
            # 1. Basic Job Stats
            jobs = self.db.query("SELECT * FROM jobs", ())
            total_jobs = len(jobs)
            
            successful_jobs = len([j for j in jobs if j.get("status") == "completed"])
            failed_jobs = len([j for j in jobs if j.get("status") == "failed"])
            
            # 2. Worker failures
            # We can parse job_events for "Stage done:" and "status=failed"
            # Or we can query the memory table which now stores outcome and summary
            memories = self.db.recall_memory(limit=1000)
            
            worker_failure_counts = {}
            total_time = 0.0
            valid_durations = 0
            
            for mem in memories:
                try:
                    summary = json.loads(mem.get("summary_json", "{}"))
                    stages = summary.get("stages", {})
                    history = summary.get("history", [])
                    failure_reason = summary.get("failure_reason", "")
                    
                    # Compute duration
                    # We can't strictly compute duration from summary without timestamps, 
                    # but we can grab job_events for true duration or estimate it if we recorded it.
                    
                    # Count failures
                    for stage_name, status in stages.items():
                        if status == "failed":
                            worker_failure_counts[stage_name] = worker_failure_counts.get(stage_name, 0) + 1
                            
                except Exception:
                    pass
            
            most_failed_worker = "None"
            if worker_failure_counts:
                most_failed_worker = max(worker_failure_counts, key=worker_failure_counts.get)
                
            metrics = {
                "total_jobs": total_jobs,
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "worker_failure_counts": worker_failure_counts,
                "most_failed_worker": most_failed_worker
            }
            
            with open(output_path, "w") as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            print(f"Failed to generate metrics report: {e}")
