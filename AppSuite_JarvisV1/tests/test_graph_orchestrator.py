import os
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock

# Ensure appsuite is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.pipeline.pipeline import Pipeline
from appsuite.core.supervisor import Supervisor
from appsuite.core.state import WorkerResult, WorkerStatus

class MockWorker:
    def __init__(self, key):
        self.key = key
        self.run_call_count = 0
        self.next_result = None

    def run(self, job, state):
        self.run_call_count += 1
        if self.next_result:
            if isinstance(self.next_result, Exception):
                raise self.next_result
            res = self.next_result
            self.next_result = None
            return res
            
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={"stage": self.key, "ok": True},
            reason="",
            metadata={"execution_time": 0.01}
        )

class TestGraphOrchestrator(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.registry = MagicMock()
        self.registry.for_job.return_value = []
        self.memory = MagicMock()
        self.memory.recall_similar.return_value = None
        
        self.templates = MagicMock()
        self.templates.resolve.return_value = {
            "id": "mock_template",
            "asset_slots": [{"role": "mock", "count": 1, "search_terms": ["mock"]}]
        }
        
        self.plugins = MagicMock()
        self.brain = MagicMock()
        self.jarvis = MagicMock()
        
        self.workers = {
            "internet": MockWorker("internet"),
            "analysis": MockWorker("analysis"),
            "blender": MockWorker("blender"),
            "godot": MockWorker("godot"),
            "validation": MockWorker("validation"),
            "deploy": MockWorker("deploy")
        }
        
        # Add search_and_fetch mock for ParallelInternetNode
        def fake_fetch(*args, **kwargs):
            time.sleep(0.01)
            return {"cache_hit": False, "source": "mock"}
        self.workers["internet"].search_and_fetch = fake_fetch
        
        self.output_dir = Path("./mock_output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Test Graph Mode Pipeline
        self.pipeline = Pipeline(
            self.db, self.registry, self.memory, self.templates,
            self.plugins, self.workers, self.output_dir, orchestrator_mode="graph"
        )
        
        self.supervisor = Supervisor(
            self.db, self.jarvis, self.pipeline, self.memory,
            scheduler_cfg={"max_concurrent_jobs": 1, "poll_interval_seconds": 0.1},
            retries_cfg={"godot_not_found": 0, "max_stage_retries": 3},
            brain=self.brain
        )
        self.pipeline.supervisor = self.supervisor
        
        for p in Path(".").glob("*_checkpoint.json"):
            p.unlink(missing_ok=True)
        # Mock health check to bypass system-level failures
        from appsuite.core.health import WorkerHealthMonitor
        WorkerHealthMonitor.preflight_check = MagicMock(return_value=(True, "OK"))

    def tearDown(self):
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        for p in Path(".").glob("*_checkpoint.json"):
            p.unlink(missing_ok=True)

    def test_graph_normal_flow(self):
        job = {"id": "graph_job1", "prompt": "test"}
        summary = self.pipeline.execute(job)
        self.assertEqual(summary["template"], "mock_template")
        self.assertIn("asset_search", summary["stages"])
        self.assertEqual(self.workers["deploy"].run_call_count, 1)

    def test_graph_retry_loop(self):
        # Make blender fail once, Supervisor should order RETRY, then it succeeds
        self.workers["blender"].next_result = WorkerResult(
            status=WorkerStatus.FAILED, data={}, reason="CRASH", metadata={}
        )
        job = {"id": "graph_job2", "prompt": "test"}
        self.pipeline.execute(job)
        self.assertEqual(self.workers["blender"].run_call_count, 2)

    def test_graph_abort(self):
        # Throw non-recoverable error
        self.workers["analysis"].next_result = Exception("FATAL_ERROR")
        job = {"id": "graph_job3", "prompt": "test"}
        with self.assertRaises(RuntimeError):
            self.pipeline.execute(job)
        self.assertEqual(self.workers["deploy"].run_call_count, 0)
        
    def test_graph_parallel_fetching(self):
        # We set template to require 10 assets
        self.templates.resolve.return_value = {
            "id": "mock_template_10",
            "asset_slots": [{"role": "mock", "count": 10, "search_terms": ["mock"]}]
        }
        job = {"id": "graph_job4", "prompt": "test"}
        t0 = time.time()
        self.pipeline.execute(job)
        t1 = time.time()
        # Sequential fetch would take > 0.1s. Parallel takes < 0.05s
        self.assertTrue(t1 - t0 < 0.08)

if __name__ == "__main__":
    unittest.main()
