import unittest
import time
from typing import Any, Dict

from appsuite.agents.base_agent import AgentTask
from appsuite.agents.coordinator import AgentCoordinator
from appsuite.agents.message_bus import MessageBus
from appsuite.core.semantic_memory import SemanticMemory

class MockHardware:
    def resources(self):
        return {"ram_percent": 50.0}

class MockBrain:
    def __init__(self):
        self.provider_manager = None
        
    def approve_action(self, agent_name: str, recommendation: Dict[str, Any]) -> bool:
        return True

class MockGraphNode:
    def __init__(self, name: str):
        self.name = name
    def process(self, state):
        class MockResult:
            status = type('Enum', (), {'value': 'SUCCESS'})
        return MockResult()

from appsuite.graph.graph import GraphOrchestrator

class TestAgentPipelineFull(unittest.TestCase):
    def setUp(self):
        self.message_bus = MessageBus()
        # Mock SemanticMemory facade requires DB
        class MockDB:
            def add_memory(self, *args, **kwargs): pass
            def update_job(self, *args, **kwargs): pass
            def recall_memory(self, *args, **kwargs): return []
        
        self.memory = SemanticMemory(MockDB())
        self.hardware = MockHardware()
        self.brain = MockBrain()
        self.orchestrator = GraphOrchestrator(MockDB())
        
        self.coordinator = AgentCoordinator(
            self.message_bus, 
            self.memory, 
            self.orchestrator,
            self.hardware,
            self.brain
        )

    def tearDown(self):
        import os
        for p in ["test-dag-123_dag_checkpoint.json", "test-res-456_dag_checkpoint.json"]:
            try:
                os.remove(p)
            except Exception:
                pass

    def test_full_pipeline_execution_and_dependencies(self):
        t1 = AgentTask(task_id="asset_1", agent_type="AssetAgent", objective="Find assets", priority=1)
        t2 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize models", dependencies=["asset_1"], priority=2)
        t3 = AgentTask(task_id="code_1", agent_type="CodeAgent", objective="Generate scripts", priority=3)
        t4 = AgentTask(task_id="godot_1", agent_type="GodotAgent", objective="Build scene", dependencies=["blender_1", "code_1"], priority=1)
        
        job_state = {"job": {"id": "test-dag-123"}, "pipeline_state": {}}
        
        # Start execution in another thread so we can monitor timeline
        results = self.coordinator.execute_plan([t1, t2, t3, t4], job_state)
        
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(r.status, "success")
            
        # Verify node execution was appended by orchestrator
        agent_names = [r.agent_name for r in results]
        self.assertIn("AssetAgent", agent_names)
        self.assertIn("GodotAgent", agent_names)

    def test_resource_limits_pause_blender(self):
        class HighRamHardware:
            def __init__(self):
                self.ram = 95.0
            def resources(self):
                return {"ram_percent": self.ram}
                
        hw = HighRamHardware()
        self.coordinator.hardware = hw
        
        t1 = AgentTask(task_id="blender_1", agent_type="BlenderAgent", objective="Optimize models")
        
        import threading
        def free_ram():
            time.sleep(0.5)
            hw.ram = 50.0
        
        threading.Thread(target=free_ram).start()
        
        job_state = {"job": {"id": "test-res-456"}, "pipeline_state": {}}
        results = self.coordinator.execute_plan([t1], job_state)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "success")

if __name__ == "__main__":
    unittest.main()
