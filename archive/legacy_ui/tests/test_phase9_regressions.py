import os
import tempfile
import unittest
from pathlib import Path

from appsuite.agents.base_agent import AgentTask
from appsuite.core.jarvis import JarvisCore
from appsuite.core.jarvis_brain import ExecutionPlan
from appsuite.db import Database
from appsuite.workers.blender_worker import BlenderWorker
from appsuite.workers.godot_worker import GodotWorker


class DummyBrain:
    def plan_execution(self, prompt, template_id=None):
        return ExecutionPlan(
            stages=["asset_search"],
            agent_tasks=[],
            reasoning="test",
            metadata={"scene_plan": {"needed_assets": [{"role": "tree", "count": 1}]}},
            template_id=template_id,
        )


class DummyTemplates:
    def resolve(self, prompt, template_id=None):
        return {"id": template_id or "generic_scene", "scene_plan": {"needed_assets": [{"role": "tree", "count": 1}]}}


class TestPhase9Regressions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "regressions.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_sqlite_database_timeout_is_set(self):
        conn = self.db._get_conn()
        self.assertEqual(getattr(conn, "timeout", 30.0), 30.0)

    def test_blender_fbx_stub_handles_missing_objects(self):
        output_dir = Path(self.tmp_dir.name) / "output"
        worker = BlenderWorker({}, {}, {}, output_dir=str(output_dir))
        stub_path = output_dir / "scene_stub.fbx"
        worker._write_fbx_stub({"ground": {}}, stub_path)
        self.assertTrue(stub_path.exists())
        content = stub_path.read_text(encoding="utf-8")
        self.assertIn("FBXHeaderExtension", content)

    def test_godot_scene_generation_handles_missing_objects(self):
        output_dir = Path(self.tmp_dir.name) / "output"
        worker = GodotWorker({}, {}, {}, output_dir=str(output_dir))
        project_dir = Path(self.tmp_dir.name) / "godot_project"
        scene_path = worker.generate_main_scene({"ground": {}, "lighting": {}}, project_dir, is_fps=False)
        self.assertTrue(scene_path.exists())
        self.assertTrue(scene_path.read_text(encoding="utf-8").startswith("[gd_scene"))

    def test_jarvis_plan_uses_scene_plan_from_execution_metadata(self):
        jarvis = JarvisCore({}, str(self.tmp_dir.name))
        jarvis._brain = DummyBrain()
        jarvis._templates = DummyTemplates()
        plan = jarvis._plan("Create a forest", "forest_template")
        self.assertEqual(plan.template_id, "forest_template")
        self.assertEqual(plan.scene_plan["needed_assets"][0]["role"], "tree")


if __name__ == "__main__":
    unittest.main()
