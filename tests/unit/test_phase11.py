from __future__ import annotations
from pathlib import Path
from appsuite.db import Database
from appsuite.core.task_queue import PersistentTaskQueue
from appsuite.core.benchmark_engine import BenchmarkEngine
from appsuite.core.semantic_memory import SemanticMemory

def test_persistent_task_queue(tmp_path):
    db_file = tmp_path / "test_queue.db"
    db = Database(db_file)
    queue = PersistentTaskQueue(db)
    
    # Register interdependent tasks
    queue.enqueue(task_id="t_sub", project_id="p1", objective="Subtask", priority=1, dependencies=["t_root"])
    queue.enqueue(task_id="t_root", project_id="p1", objective="Root task", priority=2)
    
    # Since t_sub depends on t_root, dequeuing should return t_root first
    t = queue.dequeue()
    assert t is not None
    assert t["task_id"] == "t_root"
    
    # Try dequeuing again: t_sub is waiting for t_root to be complete
    assert queue.dequeue() is None
    
    # Complete t_root
    queue.mark_completed("t_root")
    
    # Now t_sub should be runnable
    t = queue.dequeue()
    assert t is not None
    assert t["task_id"] == "t_sub"
    
    db.close()

def test_benchmark_engine(tmp_path):
    db_file = tmp_path / "test_bench.db"
    db = Database(db_file)
    be = BenchmarkEngine(db)
    
    # Record provider metrics
    be.record_metric("latency", "prov_1", 0.5)
    be.record_metric("latency", "prov_1", 0.3)
    be.record_metric("cost", "prov_1", 0.001)
    
    avg_lat = be.get_average_metric("latency", "prov_1")
    assert avg_lat == 0.4
    
    # Provider scoring and ranking
    candidates = [
        {"id": "prov_1", "priority": 1},
        {"id": "prov_2", "priority": 2}
    ]
    ranked = be.rank_providers(candidates)
    assert len(ranked) == 2
    
    db.close()

def test_active_learning_in_memory(tmp_path):
    db_file = tmp_path / "test_learning.db"
    db = Database(db_file)
    mem = SemanticMemory(db)
    
    # Add recurring failure triggers
    db.add_failure_memory("mesh_generation", "Timeout Error", {})
    db.add_failure_memory("mesh_generation", "Timeout Error", {})
    
    # Add success outcomes
    db.add_memory("job_1", "Platformer", "platformer_2d", "success", {})
    db.add_memory("job_2", "Retro side-scroller", "platformer_2d", "success", {})
    
    # Trigger active learning consolidation loop
    stats = mem.discover_and_update_strategies()
    
    assert stats["failures_discovered"] > 0
    assert stats["successes_consolidated"] > 0
    
    # Verify strategies are generated
    strategies = db.get_strategy_memories("Trigger recovery for error: Timeout Error")
    assert len(strategies) > 0
    assert "Avoid matching failure trigger" in strategies[0]["strategy"]["rule"]
    
    db.close()
