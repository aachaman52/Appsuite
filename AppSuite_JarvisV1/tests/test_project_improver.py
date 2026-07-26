import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from appsuite.core.project_improver import ProjectImprover
from appsuite.workers.base import WorkerError

class TestProjectImprover(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.memory = MagicMock()
        self.improver = ProjectImprover(self.db, self.memory)
        
    def test_categorize_failure(self):
        self.assertEqual(self.improver._categorize_failure("all_assets_imported_in_project"), "import_failure")
        self.assertEqual(self.improver._categorize_failure("godot_project_exists"), "structural_error")
        self.assertEqual(self.improver._categorize_failure("some_script_failed_to_compile"), "script_error")
        self.assertEqual(self.improver._categorize_failure("physics_collision_overlap"), "physics_error")
        
    def test_execute_repair_loop_success_first_try(self):
        validation_worker = MagicMock()
        # Mock run to return success without raising WorkerError
        validation_worker.run.return_value = {"status": "SUCCESS"}
        
        job = {"id": "1"}
        state = {}
        
        report = self.improver.execute_repair_loop(job, state, validation_worker)
        self.assertTrue(report["success"])
        self.assertEqual(len(report["attempts"]), 0)
        self.assertEqual(validation_worker.run.call_count, 1)

    @patch("appsuite.core.project_improver.ProjectImprover._apply_repair")
    @patch("appsuite.core.project_improver.ProjectImprover._rebuild_project")
    def test_execute_repair_loop_with_retries(self, mock_rebuild, mock_apply):
        validation_worker = MagicMock()
        
        # Fail first two times, pass on third
        def run_side_effect(job, state):
            if run_side_effect.calls == 0:
                run_side_effect.calls += 1
                state["validation"] = {
                    "checks": [{"name": "all_asset_files_exist", "passed": False}],
                    "passed": 0, "total": 1
                }
                raise WorkerError("Failed")
            elif run_side_effect.calls == 1:
                run_side_effect.calls += 1
                state["validation"] = {
                    "checks": [{"name": "all_asset_files_exist", "passed": False}],
                    "passed": 0, "total": 1
                }
                raise WorkerError("Failed again")
            else:
                state["validation"] = {
                    "checks": [{"name": "all_asset_files_exist", "passed": True}],
                    "passed": 1, "total": 1
                }
                return {"status": "SUCCESS"}
                
        run_side_effect.calls = 0
        validation_worker.run.side_effect = run_side_effect
        
        # DB returns a repair action
        self.db.query.return_value = [{"fix_action": "copy_default_assets"}]
        mock_apply.return_value = ["model.obj"]
        
        state = {"godot_project": "dummy_path"}
        report = self.improver.execute_repair_loop({"id": "1"}, state, validation_worker)
        
        self.assertTrue(report["success"])
        self.assertEqual(len(report["attempts"]), 2)
        
        # Memory should record failure for the first attempt that didn't fix it
        # and success for the second attempt that did
        self.assertEqual(self.memory.repair.record.call_count, 2)
        
if __name__ == "__main__":
    unittest.main()
