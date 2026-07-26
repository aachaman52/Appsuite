import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime

def generate_report():
    data_dir = Path("data")
    db_path = data_dir / "appsuite.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}. Run a generation job first.")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Execution metrics
    cursor.execute("SELECT * FROM worker_executions")
    metrics = cursor.fetchall()
    
    # Knowledge Graph Strategies
    cursor.execute("SELECT * FROM execution_graph")
    strategies = cursor.fetchall()
    
    report_lines = [
        "# AppSuite V1 Automated Benchmark Report",
        f"Generated at: {datetime.now().isoformat()}",
        "",
        "## Overall Pipeline Stability",
        "---",
        f"Total Jobs Executed: {len(strategies)}",
    ]
    
    success_count = sum(1 for s in strategies if s["final_success"])
    if strategies:
        success_rate = (success_count / len(strategies)) * 100
        report_lines.append(f"Global Success Rate: **{success_rate:.2f}%**")
    
    report_lines.extend(["", "## Worker Performance Metrics", "---"])
    
    # Aggregate worker metrics
    worker_stats = {}
    for m in metrics:
        worker = m["worker_name"]
        if worker not in worker_stats:
            worker_stats[worker] = {"count": 0, "success": 0, "time": 0.0, "cpu": 0.0, "ram": 0.0}
        
        worker_stats[worker]["count"] += 1
        if m["success"]:
            worker_stats[worker]["success"] += 1
        worker_stats[worker]["time"] += m["execution_time"]
        worker_stats[worker]["cpu"] += m["cpu_usage"]
        worker_stats[worker]["ram"] += m["ram_usage"]
        
    report_lines.append("| Worker | Executions | Success Rate | Avg Time (s) | Avg CPU (%) | Avg RAM (MB) |")
    report_lines.append("|---|---|---|---|---|---|")
    
    for worker, stats in worker_stats.items():
        count = stats["count"]
        succ_rate = (stats["success"] / count) * 100
        avg_time = stats["time"] / count
        avg_cpu = stats["cpu"] / count
        avg_ram = stats["ram"] / count
        report_lines.append(f"| {worker.capitalize()} | {count} | {succ_rate:.1f}% | {avg_time:.2f} | {avg_cpu:.1f} | {avg_ram:.1f} |")
        
    report_lines.extend(["", "## Strategy Knowledge Graph Results", "---"])
    
    if not strategies:
        report_lines.append("No complete end-to-end strategies recorded yet.")
    else:
        for s in strategies:
            status = "✅ SUCCESS" if s["final_success"] else "❌ FAILED"
            score = s["validation_score"] or 0
            time_val = s["execution_time"] or 0
            workers_used = json.loads(s["workers_used_json"]) if s.get("workers_used_json") else []
            repairs = json.loads(s["repair_actions_json"]) if s.get("repair_actions_json") else []
            
            report_lines.append(f"### Job: {s['job_id'][:8]} ({status})")
            report_lines.append(f"- **Prompt**: *{s['prompt']}*")
            report_lines.append(f"- **Genre**: {s['genre']}")
            report_lines.append(f"- **Time**: {time_val:.2f}s | **Validation Score**: {score:.1f}%")
            report_lines.append(f"- **Repair Attempts**: {len(repairs)}")
            report_lines.append(f"- **Execution Path**: `{' -> '.join(workers_used)}`")
            report_lines.append("")
    
    report_path = Path("benchmark_report.md")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Benchmark report generated successfully at {report_path.absolute()}")
    
if __name__ == "__main__":
    generate_report()
