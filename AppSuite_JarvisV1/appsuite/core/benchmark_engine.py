from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from ..db import Database

class BenchmarkEngine:
    """Measures, persists, and analyzes performance metrics for AI providers, workers, and planning/reasoning cycles."""
    
    def __init__(self, db: Database, event_bus: Optional[Any] = None, config: Optional[Any] = None) -> None:
        self.db = db
        self.event_bus = event_bus
        self.config = config
        self._init_db()
        if self.event_bus:
            self.event_bus.subscribe("PipelineCompleted", self._on_pipeline_completed)
        
    def _init_db(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                value REAL NOT NULL,
                metadata_json TEXT,
                created_at REAL NOT NULL
            );
            """
        )
        
    def record_metric(self, metric_type: str, entity_id: str, value: float, metadata: Optional[Dict[str, Any]] = None) -> None:
        now = time.time()
        meta = metadata or {}
        self.db.execute(
            """
            INSERT INTO benchmarks (metric_type, entity_id, value, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (metric_type, entity_id, value, json.dumps(meta), now)
        )
        if self.event_bus:
            self.event_bus.publish("benchmark_recorded", {"type": metric_type, "entity": entity_id, "value": value})
            
    def get_average_metric(self, metric_type: str, entity_id: str, limit: int = 50) -> float:
        rows = self.db.query(
            """
            SELECT value FROM benchmarks 
            WHERE metric_type = ? AND entity_id = ? 
            ORDER BY created_at DESC LIMIT ?
            """,
            (metric_type, entity_id, limit)
        )
        if not rows:
            return 0.0
        return sum(r["value"] for r in rows) / len(rows)

    def get_rolling_stats(self, metric_type: str, limit: int = 100) -> Dict[str, Dict[str, Any]]:
        """Returns statistics (average, count) grouped by entity_id."""
        rows = self.db.query(
            """
            SELECT entity_id, value FROM benchmarks
            WHERE metric_type = ?
            ORDER BY created_at DESC
            """,
            (metric_type,)
        )
        
        stats: Dict[str, List[float]] = {}
        for r in rows:
            stats.setdefault(r["entity_id"], []).append(r["value"])
            
        result = {}
        for entity, values in stats.items():
            recent = values[:limit]
            result[entity] = {
                "average": sum(recent) / len(recent) if recent else 0.0,
                "count": len(values)
            }
        return result

    def get_provider_score(self, provider_id: str, model_name: str) -> float:
        """Computes a weighted sorting score for LLM providers. Lower is better."""
        avg_latency = self.get_average_metric("latency", provider_id) or 1.0
        avg_cost = self.get_average_metric("cost", provider_id) or 0.0
        avg_failure = self.get_average_metric("failure", provider_id) or 0.0 # 0.0 means perfect success
        
        # Weighted metric (adjust weight parameters as needed)
        score = (avg_latency * 0.4) + (avg_cost * 10000.0 * 0.4) + (avg_failure * 10.0 * 0.2)
        return score

    def rank_providers(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sorts provider list dynamically based on measured scores."""
        def sorting_key(p: Dict[str, Any]) -> float:
            # First level priority check
            base_priority = p.get("priority", 100)
            score = self.get_provider_score(p["id"], p.get("model", ""))
            # Integrate priority into score ranking
            return base_priority * 1.5 + score
            
        return sorted(candidates, key=sorting_key)

    def _on_pipeline_completed(self, event: Dict[str, Any]) -> None:
        if self.config and not self.config.get("benchmarks", {}).get("enabled", True):
            return
        self.generate_reports()
        
    def generate_reports(self) -> None:
        import sqlite3
        from pathlib import Path
        from datetime import datetime
        
        out_dir = Path("output") if not self.config else self.config.abs_path("output_dir")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # We can extract from worker_executions and execution_graph directly 
        # (similar to the generate_benchmark_report script)
        strategies = self.db.get_execution_graphs(limit=100)
        
        report_lines = [
            "# AppSuite V1 Automated Benchmark Report",
            f"Generated at: {datetime.now().isoformat()}",
            "",
            "## Overall Pipeline Stability",
            "---",
            f"Total Jobs Executed: {len(strategies)}",
        ]
        
        success_count = sum(1 for s in strategies if s.get("final_success"))
        if strategies:
            success_rate = (success_count / len(strategies)) * 100
            report_lines.append(f"Global Success Rate: **{success_rate:.2f}%**")
            
        report_lines.extend(["", "## Worker Performance Metrics", "---"])
        
        workers = ["internet", "analysis", "blender", "godot", "code", "validation", "deploy"]
        report_lines.append("| Worker | Executions | Success Rate | Avg Time (s) | Avg CPU (%) | Avg RAM (MB) |")
        report_lines.append("|---|---|---|---|---|---|")
        
        json_data = {"global_success": success_rate if strategies else 0, "workers": {}, "jobs": []}
        
        for w in workers:
            stats = self.db.get_worker_stats(w)
            if stats["total_runs"] > 0:
                report_lines.append(f"| {w.capitalize()} | {stats['total_runs']} | {stats['success_rate']*100:.1f}% | {stats['avg_runtime']:.2f} | {stats['avg_cpu']:.1f} | {stats['avg_ram']:.1f} |")
                json_data["workers"][w] = stats
                
        report_lines.extend(["", "## Strategy Knowledge Graph Results", "---"])
        
        for s in strategies:
            status = "✅ SUCCESS" if s["final_success"] else "❌ FAILED"
            score = s["validation_score"] or 0
            time_val = s["execution_time"] or 0
            workers_used = s["workers_used"]
            repairs = s["repair_actions"]
            
            report_lines.append(f"### Job: {s['job_id'][:8]} ({status})")
            report_lines.append(f"- **Prompt**: *{s['prompt']}*")
            report_lines.append(f"- **Genre**: {s['genre']}")
            report_lines.append(f"- **Time**: {time_val:.2f}s | **Validation Score**: {score:.1f}%")
            report_lines.append(f"- **Repair Attempts**: {len(repairs)}")
            report_lines.append(f"- **Execution Path**: `{' -> '.join(workers_used)}`")
            report_lines.append("")
            
            json_data["jobs"].append(s)
            
        (out_dir / "benchmark_report.md").write_text("\n".join(report_lines), encoding="utf-8")
        with open(out_dir / "benchmark_report.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4)
