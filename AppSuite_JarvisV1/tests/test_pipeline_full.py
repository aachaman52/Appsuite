import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure we can import appsuite
sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.core.state import WorkerResult, WorkerStatus
from appsuite.pipeline.pipeline import Pipeline
from appsuite.core.supervisor import Supervisor, SupervisorAction

class MockWorker:
    def __init__(self, key):
        self.key = key
        self.run_call_count = 0
        self.next_result = None
        self.results_sequence = []

    def run(self, job, state):
        self.run_call_count += 1
        if self.results_sequence:
            result = self.results_sequence.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        if self.next_result:
            return self.next_result
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={"stage": self.key, "ok": True},
            reason="",
            metadata={"execution_time": 0.1}
        )

    def search_and_fetch(self, job_id, role, term):
        self.run_call_count += 1
        if self.results_sequence and isinstance(self.results_sequence[0], Exception):
            raise self.results_sequence[0]
        return {"file_path": "mock.obj", "cache_hit": False, "source": "mock"}

class TestPipelineFull(unittest.TestCase):
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
        
        self.output_dir = Path("./mock_output")
        self.output_dir.mkdir(exist_ok=True)
        
        self.pipeline = Pipeline(
            self.db, self.registry, self.memory, self.templates,
            self.plugins, self.workers, self.output_dir
        )
        
        self.supervisor = Supervisor(
            self.db, self.jarvis, self.pipeline, self.memory,
            scheduler_cfg={"max_concurrent_jobs": 1, "poll_interval_seconds": 0.1},
            retries_cfg={"godot_not_found": 0, "max_stage_retries": 1},
            brain=self.brain
        )
        self.pipeline.supervisor = self.supervisor
        
        # Disable true health checks for mocking
        from appsuite.core.health import WorkerHealthMonitor
        WorkerHealthMonitor.preflight_check = MagicMock(return_value=(True, "OK"))

    def tearDown(self):
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_normal_success(self):
        job = {"id": "job1", "prompt": "test"}
        summary = self.pipeline.execute(job)
        self.assertEqual(summary["template"], "mock_template")
        self.assertEqual(self.workers["internet"].run_call_count, 1)
        self.assertEqual(self.workers["deploy"].run_call_count, 1)

    def test_missing_godot_abort(self):
        # Supervisor should abort if worker raises specific exception
        # Let's say godot worker crashes with GODOT_NOT_FOUND
        self.workers["godot"].results_sequence = [Exception("GODOT_NOT_FOUND")]
        
        job = {"id": "job2", "prompt": "test"}
        with self.assertRaises(RuntimeError) as ctx:
            self.pipeline.execute(job)
            
        self.assertIn("aborted", str(ctx.exception))
        self.assertEqual(self.workers["internet"].run_call_count, 1)
        self.assertEqual(self.workers["deploy"].run_call_count, 0)

    def test_missing_asset_reroute(self):
        # blender needs asset -> goes back to internet -> blender
        self.workers["blender"].results_sequence = [
            WorkerResult(status=WorkerStatus.NEED_ASSET, data={}, reason="MATERIAL_NOT_ASSIGNED", metadata={}),
            WorkerResult(status=WorkerStatus.SUCCESS, data={}, reason="", metadata={})
        ]
        
        job = {"id": "job3", "prompt": "test"}
        summary = self.pipeline.execute(job)
        print("MISSING ASSET HISTORY:", summary.get("history"))
        print("MISSING ASSET FAILURE:", summary.get("failure_reason"))
        
        self.assertEqual(self.workers["blender"].run_call_count, 2)
        self.assertEqual(self.workers["internet"].run_call_count, 2)
        
    def test_memory_reuse(self):
        self.memory.recall_similar.return_value = {"job_id": "job0"}
        mock_asset_file = self.output_dir / "asset.glb"
        mock_asset_file.write_text("dummy")
        
        self.registry.for_job.return_value = [
            {"file_path": str(mock_asset_file), "role": "mock", "normalized_asset": "mock.tscn"}
        ]
        
        job = {"id": "job4", "prompt": "test"}
        summary = self.pipeline.execute(job)
        
        self.assertTrue(summary["assets_reused"])
        self.assertEqual(self.workers["internet"].run_call_count, 0)
        self.assertEqual(self.workers["analysis"].run_call_count, 1)
        
    def test_worker_crash_converts_to_failed(self):
        self.workers["analysis"].results_sequence = [Exception("some random crash")] * 5
        
        job = {"id": "job5", "prompt": "test"}
        with self.assertRaises(RuntimeError) as ctx:
            self.pipeline.execute(job)
            
        self.assertIn("aborted", str(ctx.exception).lower())
        self.assertGreaterEqual(self.workers["analysis"].run_call_count, 1)

if __name__ == "__main__":
    unittest.main()
