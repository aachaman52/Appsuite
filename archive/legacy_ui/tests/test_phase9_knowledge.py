import tempfile
import unittest
from pathlib import Path

from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.worker_scorer import WorkerScoreRegistry
from appsuite.db import Database


class TestPhase9Knowledge(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "knowledge.db"
        self.db = Database(self.db_path)
        self.memory = SemanticMemory(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_strategy_similarity_and_worker_scores(self):
        self.memory.strategy.add_strategy(
            "build a castle",
            {"worker": "BlenderAgent", "job_id": "job1", "plan": "castle"},
            "success"
        )
        self.memory.strategy.add_strategy(
            "build a castle",
            {"worker": "BlenderAgent", "job_id": "job2", "plan": "castle"},
            "success"
        )
        self.memory.strategy.add_strategy(
            "build a castle",
            {"worker": "CodeAgent", "job_id": "job3", "plan": "script"},
            "failed"
        )

        similar = self.memory.strategy.get_similar_strategies("castle scene creation", threshold=0.1)
        self.assertTrue(len(similar) >= 1)
        self.assertIn("similarity_score", similar[0])

        registry = WorkerScoreRegistry(self.memory)
        scores = registry.score_workers()
        self.assertIn("BlenderAgent", scores)
        self.assertGreater(scores.get("BlenderAgent", 0.0), scores.get("CodeAgent", -1.0))


if __name__ == "__main__":
    unittest.main()
