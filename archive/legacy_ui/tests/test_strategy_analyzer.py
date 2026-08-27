import unittest
from pathlib import Path
from appsuite.db import Database
from appsuite.core.strategy_analyzer import StrategyAnalyzer

class TestStrategyAnalyzer(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_execution_graph.db")
        if self.db_path.exists():
            self.db_path.unlink()
        self.db = Database(self.db_path)
        self.analyzer = StrategyAnalyzer(self.db)
        
        # Seed test data
        # Strategy A: high success
        for _ in range(5):
            self.db.add_execution_graph(
                "job1", "test prompt", "fps", "strategy_a", "kenney", "claude-3-5",
                ["internet", "godot"], ["repair_import"], 1.0, 10.0, True
            )
        # Strategy B: low success
        for _ in range(5):
            self.db.add_execution_graph(
                "job2", "test prompt", "rpg", "strategy_b", "sketchfab", "claude-3-5",
                ["internet", "godot"], [], 0.0, 15.0, False
            )
            
    def tearDown(self):
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_highest_success_rate_strategy(self):
        result = self.analyzer.highest_success_rate_strategy()
        self.assertEqual(result["strategy"], "strategy_a")
        self.assertEqual(result["success_rate"], 1.0)

    def test_best_asset_provider_for_genre(self):
        # Add some specific FPS runs
        self.db.add_execution_graph("j", "fps", "fps", "s", "poly_pizza", "c", [], [], 1.0, 5.0, True)
        self.db.add_execution_graph("j", "fps", "fps", "s", "poly_pizza", "c", [], [], 1.0, 5.0, True)
        self.db.add_execution_graph("j", "fps", "fps", "s", "kenney", "c", [], [], 0.0, 5.0, False)
        
        # We seeded 5 kenney successes for fps in setUp
        # Now poly_pizza has 2, kenney has 5 successes.
        prov = self.analyzer.best_asset_provider_for_genre("fps")
        self.assertEqual(prov, "poly_pizza")
        
        # What about rpg? We seeded 5 sketchfab failures for rpg.
        # Let's add 1 sketchfab success.
        self.db.add_execution_graph("j", "rpg", "rpg", "s", "sketchfab", "c", [], [], 1.0, 5.0, True)
        prov = self.analyzer.best_asset_provider_for_genre("rpg")
        self.assertEqual(prov, "sketchfab")

    def test_best_repair_action(self):
        best = self.analyzer.best_repair_action()
        self.assertEqual(best, "repair_import")

    def test_failing_worker_combinations(self):
        fails = self.analyzer.failing_worker_combinations()
        self.assertEqual(fails[0][0], tuple(sorted(["internet", "godot"])))
        self.assertEqual(fails[0][1], 5)

    def test_average_execution_time(self):
        avg = self.analyzer.average_execution_time("strategy_a")
        self.assertAlmostEqual(avg, 10.0)
        avg_b = self.analyzer.average_execution_time("strategy_b")
        self.assertAlmostEqual(avg_b, 15.0)

    def test_confidence_score(self):
        conf_a = self.analyzer.confidence_score("strategy_a")
        self.assertAlmostEqual(conf_a, 1.0)
        conf_b = self.analyzer.confidence_score("strategy_b")
        self.assertAlmostEqual(conf_b, 0.0)

if __name__ == "__main__":
    unittest.main()
