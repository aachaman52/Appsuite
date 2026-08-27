import unittest
import json
from unittest.mock import MagicMock
from appsuite.core.jarvis_memory import JarvisMemory
from appsuite.core.supervisor_intelligence import SupervisorIntelligence, MemoryContext

class TestMemoryDrivenPlanning(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.memory = JarvisMemory(self.db)
        self.intelligence = SupervisorIntelligence(self.db, self.memory)

    def test_memory_context_built_correctly(self):
        def mock_query(sql, params=None):
            if "success_memory WHERE" in sql:
                return []
            if "strategy_memory WHERE" in sql:
                return []
            if "failure_memory WHERE" in sql:
                return []
            if "asset_memory WHERE success_count > fail_count" in sql:
                return [{"asset_name": "kenney_car", "success_count": 5, "fail_count": 0}]
            if "asset_memory WHERE fail_count > success_count" in sql:
                return [{"asset_name": "sketchfab_model", "asset_source": "sketchfab", "success_count": 0, "fail_count": 6}]
            if "workers_used_json FROM success_memory" in sql:
                return [{"workers_used_json": '["internet", "analysis"]'}]
            if "context_json FROM failure_memory" in sql:
                return [{"context_json": '{"worker": "blender"}'}]
            if "FROM repair_memory" in sql:
                return [{"error_pattern": "import_fail", "fix_action": "convert_fbx", "success_count": 2}]
            return []
            
        self.db.query.side_effect = mock_query
        
        ctx = self.intelligence._build_planning_context("Create a car")
        
        mem_ctx = ctx.memory_context
        self.assertIsNotNone(mem_ctx)
        self.assertEqual(len(mem_ctx.failed_assets), 1)
        self.assertEqual(mem_ctx.failed_assets[0]["asset_source"], "sketchfab")
        self.assertIn("blender", mem_ctx.failed_workers)
        self.assertEqual(len(mem_ctx.repair_history), 1)

    def test_planner_decisions_based_on_memory(self):
        # Setup context with failures that trigger rules
        ctx = self.intelligence._build_planning_context("Create a car")
        mem_ctx = MemoryContext()
        mem_ctx.failed_assets = [{"asset_source": "sketchfab"} for _ in range(5)]
        mem_ctx.failed_workers = ["blender", "godot"]
        mem_ctx.repair_history = [{"fix_action": "clear_cache", "success_count": 2}]
        ctx.memory_context = mem_ctx
        
        # Override the context builder to return our injected context
        self.intelligence._build_planning_context = MagicMock(return_value=ctx)
        
        # Mock DebateRoom
        self.intelligence.debate_room.hold_debate = MagicMock()
        mock_proposal = MagicMock()
        mock_proposal.worker_sequence = ["internet", "blender", "godot"]
        mock_proposal.asset_hints = {}
        mock_proposal.template_id = "test"
        mock_proposal.agent_name = "Planner"
        mock_proposal.reasoning = "Base reasoning"
        self.intelligence.debate_room.hold_debate.return_value = mock_proposal

        plan = self.intelligence.build_execution_plan("Create a car", "job_123")
        
        # Check rule 1: Sketchfab failed -> Kenney
        self.assertEqual(plan.asset_hints.get("source"), "kenney")
        self.assertIn("Planner Decision: Use Kenney", plan.reasoning)
        
        # Check rule 2 & 3: Blender & Godot failed -> modifiers
        self.assertIn("reduce_asset_count", plan.pipeline_modifiers)
        self.assertIn("Planner Decision: Reduce asset count", plan.reasoning)
        
        self.assertIn("convert_fbx_to_glb", plan.pipeline_modifiers)
        self.assertIn("Planner Decision: Convert FBX to GLB first", plan.reasoning)
        
        # Check rule 4: Repair history
        self.assertIn("apply_repair:clear_cache", plan.pipeline_modifiers)
        self.assertIn("Planner Decision: Apply clear_cache", plan.reasoning)
        
        # Ensure StrategyMemory was updated
        self.db.add_strategy_memory.assert_called()

if __name__ == '__main__':
    unittest.main()
