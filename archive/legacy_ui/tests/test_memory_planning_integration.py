import unittest
import os
import json
import sqlite3
from pathlib import Path
from appsuite.db import Database
from appsuite.core.jarvis_memory import JarvisMemory
from appsuite.core.supervisor_intelligence import SupervisorIntelligence

class TestMemoryPlanningIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_planning.db")
        if self.db_path.exists():
            os.remove(self.db_path)
            
        self.db = Database(self.db_path)
        self.memory = JarvisMemory(self.db)
        self.intelligence = SupervisorIntelligence(self.db, self.memory)

    def tearDown(self):
        self.db.close()
        if self.db_path.exists():
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_end_to_end_planning_with_memory(self):
        # 1. Populate Memory with Failures
        
        # 5 Sketchfab failures
        for i in range(5):
            self.memory.record_asset_result(f"model_{i}", "sketchfab", "general", False, "import error")
            
        # Blender failure
        self.memory.record_failure("make a car", "blender", "blender_process", "timeout error", "")
        
        # Repair strategy
        self.memory.repair.record("timeout error", "increase_timeout", True)
        self.memory.repair.record("timeout error", "increase_timeout", True)

        # 2. Run planning
        plan = self.intelligence.build_execution_plan("make a car", "test_job_1")
        
        # 3. Assert Memory Context and modifications
        self.assertIsNotNone(plan.planning_context)
        mem_ctx = plan.planning_context.memory_context
        self.assertIsNotNone(mem_ctx)
        
        # Asset hints should prefer Kenney due to Sketchfab failures
        self.assertEqual(plan.asset_hints.get("source"), "kenney")
        
        # Modifiers should include reduce_asset_count because of blender failure
        self.assertIn("reduce_asset_count", plan.pipeline_modifiers)
        
        # Modifiers should include the successful repair action
        self.assertIn("apply_repair:increase_timeout", plan.pipeline_modifiers)
        
        # 4. Verify Debate Room usage of memory context
        # (This is harder to test directly without mocking, but the confidence score 
        # should reflect it, or we can just ensure it doesn't crash).
        
        # 5. Verify StrategyMemory recorded the planner's decisions
        strategies = self.db.query("SELECT * FROM strategy_memory WHERE prompt='make a car' ORDER BY created_at DESC")
        self.assertTrue(len(strategies) > 0)
        strategy = json.loads(strategies[0]["strategy_json"])
        self.assertEqual(strategy["repair_strategy"], ";".join(plan.pipeline_modifiers))
        self.assertEqual(strategies[0]["outcome"], "planned")

if __name__ == '__main__':
    unittest.main()
