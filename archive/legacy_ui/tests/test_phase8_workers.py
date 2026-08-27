"""Tests for Phase 8 Autonomous Worker Intelligence Layer."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from appsuite.core.state import WorkerStatus, WorkerResult
from appsuite.workers.internet_worker import InternetWorker
from appsuite.workers.blender_worker import BlenderWorker
from appsuite.workers.godot_worker import GodotWorker
from appsuite.workers.code_worker import CodeWorker
from appsuite.workers.validation_worker import ValidationWorker
from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.asset_registry import AssetRegistry
from appsuite.db import Database


class TestPhase8WorkerIntelligence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_appsuite.db"
        self.db = Database(str(self.db_path))
        self.registry = AssetRegistry(self.db)
        self.context = {"db": self.db, "registry": self.registry}

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_internet_worker_contract_and_recovery(self):
        # Instantiate worker
        worker = InternetWorker(
            {}, {}, self.context,
            provider_manager=MagicMock(), registry=self.registry,
            assets_dir=self.temp_dir, cache_dir=self.temp_dir
        )
        
        # Test default contract lifecycle
        self.assertTrue(worker.initialize())
        h_ok, h_msg = worker.health_check()
        self.assertTrue(h_ok)
        
        job = {"id": "job_1", "prompt": "find tree 3d asset"}
        state = {
            "template": {
                "asset_slots": [{"role": "tree", "count": 1}]
            }
        }
        
        plan = worker.plan(job, state)
        self.assertIn("resolve_asset:tree", plan)
        
        # Simulate a crash during execution to trigger recovery
        with patch.object(worker, "run", side_effect=ValueError("Simulated run failure")):
            res = worker.process(job, state)
            
        self.assertEqual(res.status, WorkerStatus.SUCCESS)
        self.assertTrue(res.metadata.get("recovered"))
        self.assertEqual(len(state["assets"]), 1)
        self.assertEqual(state["assets"][0]["source"], "local_library")
        
        # Test report
        rep = worker.report(job, state)
        self.assertEqual(rep["worker"], "internet")
        self.assertEqual(rep["assets_fetched_count"], 1)

    def test_blender_worker_contract_and_geometry_repair(self):
        worker = BlenderWorker({}, {}, self.context, output_dir=Path(self.temp_dir))
        
        # Verify contract methods
        self.assertTrue(worker.initialize())
        plan = worker.plan({"id": "j1"}, {"assets": [{"route": "blender_to_godot"}]})
        self.assertIn("optimize_assets_in_blender", plan)
        
        # Verify recovery
        job = {"id": "job_2", "prompt": "build building"}
        state = {
            "scene_layout": {"objects": [{"role": "house", "source_file": "house.glb", "location": [0,0,0], "scale": [1,1,1]}]},
            "assets": [{"route": "blender_to_godot"}]
        }
        
        # Recover path should generate a scene.fbx stub
        res = worker.recover(job, state, ValueError("Blender not found"))
        self.assertEqual(res.status, WorkerStatus.SUCCESS)
        self.assertTrue(res.data.get("recovered"))
        self.assertTrue(Path(state["fbx_path"]).exists())

    def test_godot_worker_contract_and_recovery(self):
        worker = GodotWorker({}, {}, self.context, output_dir=Path(self.temp_dir))
        
        # Verify plan
        plan = worker.plan({}, {})
        self.assertIn("initialize_godot_project", plan)
        
        # Verify recovery creates a working basic scene & project
        job = {"id": "job_3"}
        state = {}
        res = worker.recover(job, state, ValueError("Godot binary failed"))
        self.assertEqual(res.status, WorkerStatus.SUCCESS)
        self.assertTrue(res.data.get("recovered"))
        self.assertTrue(Path(state["godot_project"]).exists())
        self.assertTrue(Path(state["main_scene"]).exists())

    def test_code_worker_contract_and_syntax_recovery(self):
        # Create code worker
        pm = MagicMock()
        pm.generate_text.return_value = "extends Node3D\nfunc _ready():\n    pass"
        worker = CodeWorker({}, {}, self.context, provider_manager=pm)
        
        # Verify plan
        job = {"id": "job_4", "prompt": "fps shooter movement script"}
        state = {"project_path": self.temp_dir}
        plan = worker.plan(job, state)
        self.assertIn("plan_architecture:player.gd", plan)
        
        # Verify successful generation
        with patch("subprocess.run") as mock_run:
            # Mock successful Godot syntax check
            mock_run.return_value.returncode = 0
            res = worker.process(job, state)
            
        self.assertEqual(res.status, WorkerStatus.SUCCESS)
        self.assertTrue(Path(res.data["script_path"]).exists())
        
        # Verify report
        rep = worker.report(job, state)
        self.assertEqual(rep["worker"], "code")
        self.assertEqual(rep["scripts_count"], 1)

    def test_validation_worker_contract_and_self_correction(self):
        worker = ValidationWorker({}, {}, self.context)
        
        job = {"id": "job_5"}
        state = {
            "assets": [{"file_path": str(Path(self.temp_dir) / "model.glb"), "route": "direct_godot"}],
            "godot_project": self.temp_dir,
            "scene_layout": {
                "objects": [{"role": "tree"}],
                "lighting": True
            }
        }
        # Write dummy model file and project structure
        Path(state["assets"][0]["file_path"]).write_text("dummy", encoding="utf-8")
        project_dir = Path(self.temp_dir)
        (project_dir / "Scenes").mkdir(parents=True, exist_ok=True)
        (project_dir / "Scenes" / "main.tscn").write_text("[gd_scene]", encoding="utf-8")
        (project_dir / "project.godot").write_text("", encoding="utf-8")
        
        # Run validation recovery - it should copy the asset and create the .import file
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError() # Skip actual Godot run
            res = worker.recover(job, state, ValueError("Initial validation failed"))
            
        self.assertEqual(res.status, WorkerStatus.SUCCESS)
        # Check that files were copied and imports created
        copied_asset = Path(self.temp_dir) / "Assets" / "model.glb"
        self.assertTrue(copied_asset.exists())
        self.assertTrue(Path(str(copied_asset) + ".import").exists())


if __name__ == "__main__":
    unittest.main()
