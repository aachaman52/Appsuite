import os
import tempfile
import unittest
from pathlib import Path

from appsuite.db import Database
from appsuite.core.world_model import WorldModel


class TestPhase9WorldModel(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "world_model.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_world_model_persists_updates_and_reads_back(self):
        job_id = "job-world-1"
        model = WorldModel(job_id, self.db)
        model.update("assets", [{"id": "asset-1", "role": "environment"}])
        model.update("scene", {"main_scene": "Scenes/main.tscn"})

        self.assertEqual(model.get("assets")[0]["id"], "asset-1")
        self.assertEqual(model.get("scene")["main_scene"], "Scenes/main.tscn")

        # Reload from the same database and verify persistence
        model_reload = WorldModel(job_id, self.db)
        self.assertEqual(model_reload.get("assets")[0]["id"], "asset-1")
        self.assertEqual(model_reload.get("scene")["main_scene"], "Scenes/main.tscn")


if __name__ == "__main__":
    unittest.main()
