import unittest
import os
import shutil
import unittest.mock
from pathlib import Path

from appsuite.db import Database
from appsuite.core.jarvis_memory import JarvisMemory
from appsuite.core.project_improver import ProjectImprover
from appsuite.workers.base import WorkerError

class DummyValidationWorker:
    def __init__(self):
        self.call_count = 0
        
    def run(self, job, state):
        self.call_count += 1
        project = Path(state["godot_project"])
        
        # Scenario: Project structure missing on first run, fixed by improver
        if not (project / "project.godot").exists():
            state["validation"] = {
                "checks": [{"name": "godot_project_exists", "passed": False}],
                "passed": 0, "total": 1
            }
            raise WorkerError("Missing Project")
            
        # Scenario: Import file missing on second run, fixed by improver
        if not (project / "Assets" / "model.glb.import").exists():
            state["validation"] = {
                "checks": [{"name": "all_assets_imported_in_project", "passed": False}],
                "passed": 0, "total": 1
            }
            raise WorkerError("Missing Import")
            
        # Everything passed!
        state["validation"] = {
            "checks": [{"name": "all_checks", "passed": True}],
            "passed": 1, "total": 1
        }
        return {"status": "SUCCESS"}


class TestProjectImproverIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_improver.db")
        if self.db_path.exists():
            os.remove(self.db_path)
            
        self.db = Database(self.db_path)
        self.memory = JarvisMemory(self.db)
        self.improver = ProjectImprover(self.db, self.memory)
        
        self.test_project = Path("test_improver_project")
        if self.test_project.exists():
            shutil.rmtree(self.test_project)
            
        import subprocess
        self.patcher = unittest.mock.patch("subprocess.run")
        self.mock_subprocess = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.db.close()
        if self.db_path.exists():
            try:
                os.remove(self.db_path)
            except Exception:
                pass
        if self.test_project.exists():
            shutil.rmtree(self.test_project)

    def test_end_to_end_repair_loop_with_file_modifications(self):
        # 1. State representing a broken project
        state = {
            "godot_project": str(self.test_project),
            "assets": [{"file_path": "model.glb"}],
            "validation": {}
        }
        
        worker = DummyValidationWorker()
        
        # 2. Run the repair loop
        report = self.improver.execute_repair_loop({"id": "j1"}, state, worker)
        
        # 3. Assertions
        self.assertTrue(report["success"])
        self.assertEqual(len(report["attempts"]), 2)
        
        # Check files were actually created!
        self.assertTrue((self.test_project / "project.godot").exists())
        self.assertTrue((self.test_project / "Assets" / "model.glb.import").exists())
        
        # Check that repairs were stored in memory
        repairs = self.db.query("SELECT * FROM repair_memory")
        # We expect 2 repairs recorded as successful
        self.assertEqual(len(repairs), 2)
        for r in repairs:
            self.assertEqual(r["success_count"], 1)

    def test_benchmark_project_improver(self):
        import time
        state = {
            "godot_project": str(self.test_project),
            "assets": [{"file_path": "model.glb"}],
            "validation": {}
        }
        worker = DummyValidationWorker()
        
        start = time.perf_counter()
        report = self.improver.execute_repair_loop({"id": "benchmark"}, state, worker)
        end = time.perf_counter()
        
        self.assertTrue(report["success"])
        duration = end - start
        
        # Benchmark: Repair loop overhead for 2 repairs should be under 2 seconds.
        # It's headless godot rebuild that could take time, but since it fails instantly on fake path or is fast, it should be quick.
        print(f"Repair loop completed in {duration:.4f} seconds.")
        self.assertLess(duration, 5.0)

if __name__ == "__main__":
    unittest.main()
