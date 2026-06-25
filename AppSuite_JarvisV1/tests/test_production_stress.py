import os
import sys
import time
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.pipeline.pipeline import Pipeline
from appsuite.core.supervisor import Supervisor
from appsuite.core.state import WorkerResult, WorkerStatus
from appsuite.graph.graph import GraphOrchestrator
from appsuite.graph.nodes import BaseNode, ParallelInternetNode
from appsuite.graph.router import DecisionNode

class MockWorker:
    def __init__(self, key):
        self.key = key
        self.should_crash = False
        self.should_fail = False
        
    def run(self, job, state):
        if self.should_crash:
            raise Exception(f"Simulated {self.key} crash")
        if self.should_fail:
            return WorkerResult(WorkerStatus.FAILED, reason="Simulated failure", metadata={})
            
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={"stage": self.key, "ok": True},
            reason="",
            metadata={"execution_time": 0.01}
        )
        
    def search_and_fetch(self, job_id, role, term):
        if self.should_crash:
            raise Exception("Network Error")
        return {"file_path": "mock.obj", "cache_hit": False, "source": "mock"}

class TestProductionStress(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.registry = MagicMock()
        self.memory = MagicMock()
        self.memory.recall_similar.return_value = None
        self.templates = MagicMock()
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
            self.plugins, self.workers, self.output_dir, orchestrator_mode="graph"
        )
        
        self.supervisor = Supervisor(
            self.db, self.jarvis, self.pipeline, self.memory,
            scheduler_cfg={"max_concurrent_jobs": 1, "poll_interval_seconds": 0.1},
            retries_cfg={"max_stage_retries": 1},
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
        for p in Path(".").glob("*_checkpoint.json"):
            p.unlink(missing_ok=True)

    def test_100_asset_fetch(self):
        self.templates.resolve.return_value = {
            "id": "100_asset_template",
            "asset_slots": [{"role": "mock", "count": 100, "search_terms": ["mock"]}]
        }
        job = {"id": "job_100_assets", "prompt": "test"}
        t0 = time.time()
        summary = self.pipeline.execute(job)
        t1 = time.time()
        self.assertIn("cloud_deploy", summary["stages"])
        self.assertEqual(summary["stages"]["cloud_deploy"], "success")

    def test_blender_crash_recovery(self):
        self.templates.resolve.return_value = {
            "id": "mock_template",
            "asset_slots": [{"role": "mock", "count": 1, "search_terms": ["mock"]}]
        }
        self.workers["blender"].should_crash = True
        
        # Test that it fails and aborts instead of taking down the process
        job = {"id": "job_blender_crash", "prompt": "test"}
        with self.assertRaises(RuntimeError):
            self.pipeline.execute(job)
            
        self.assertTrue(Path("job_blender_crash_checkpoint.json").exists())

    def test_checkpoint_resume(self):
        self.templates.resolve.return_value = {
            "id": "mock_template",
            "asset_slots": [{"role": "mock", "count": 1, "search_terms": ["mock"]}]
        }
        # Force a checkpoint creation where internet completed successfully
        from appsuite.graph.state import GraphState
        state = GraphState(job={"id": "job_resume"}, pipeline_state={"template": self.templates.resolve.return_value}, current_node="blender_import")
        with open("job_resume_checkpoint.json", "w") as f:
            json.dump(state.to_dict(), f)
            
        job = {"id": "job_resume", "prompt": "test"}
        summary = self.pipeline.execute(job)
        
        # The history should show it started from blender_import, not asset_search
        self.assertEqual(summary["history"][0], "blender_import")
        self.assertEqual(summary["stages"]["cloud_deploy"], "success")

if __name__ == "__main__":
    unittest.main()
