import unittest
from typing import Any, Dict

from appsuite.agents.base_agent import AgentResult, AgentTask
from appsuite.agents.asset_agent import AssetAgent
from appsuite.agents.blender_agent import BlenderAgent
from appsuite.agents.godot_agent import GodotAgent
from appsuite.agents.code_agent import CodeAgent
from appsuite.agents.coordinator import AgentCoordinator
from appsuite.agents.message_bus import MessageBus

class MockMemory:
    def __init__(self):
        self.agent_history = []
        
    def store_agent_strategy(self, agent_name: str, result: AgentResult):
        self.agent_history.append({"agent_name": agent_name, "data": result})

    def recall_agent_strategy(self, agent_name: str):
        return [h["data"] for h in self.agent_history if h["agent_name"] == agent_name]

from appsuite.graph.graph import GraphOrchestrator

class MockDB:
    def add_event(self, *args, **kwargs): pass

class TestAgents(unittest.TestCase):
    def setUp(self):
        self.message_bus = MessageBus()
        self.memory = MockMemory()
        self.orchestrator = GraphOrchestrator(MockDB())
        self.coordinator = AgentCoordinator(self.message_bus, self.memory, orchestrator=self.orchestrator)

    def tearDown(self):
        import os
        for p in ["test-1-abc_dag_checkpoint.json", "test-fail-abc_dag_checkpoint.json", "mem-1-abc_dag_checkpoint.json", "conflict-1-abc_dag_checkpoint.json"]:
            try:
                os.remove(p)
            except Exception:
                pass

    def test_multiple_agents_executing_together(self):
        job_state = {"job": {"id": "test-1-abc"}, "pipeline_state": {}}
        t1 = AgentTask("1", "AssetAgent", "test")
        t2 = AgentTask("2", "CodeAgent", "test")
        results = self.coordinator.execute_plan([t1, t2], job_state)
        
        self.assertEqual(len(results), 2)
        names = [r.agent_name for r in results]
        self.assertIn("AssetAgent", names)
        self.assertIn("CodeAgent", names)
        
        for r in results:
            self.assertEqual(r.status, "success")

    def test_agent_failure_recovery(self):
        class FailingAgent(AssetAgent):
            def execute_tools(self, plan: Any, job_state=None) -> Any:
                raise ValueError("Simulated random crash")
                
        self.coordinator.agent_registry["AssetAgent"] = FailingAgent("AssetAgent", self.message_bus, self.memory)
        
        job_state = {"job": {"id": "test-fail-abc"}, "pipeline_state": {}}
        t1 = AgentTask("fail1", "AssetAgent", "test fail")
        results = self.coordinator.execute_plan([t1], job_state)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "failed")
        self.assertIn("Simulated random crash", results[0].output.get("error", ""))
        self.assertEqual(results[0].confidence, 0.0)

    def test_communication_failure(self):
        # Even if message bus is empty, agents should not crash indefinitely
        # Test the timeout in message bus receive
        import queue
        q = self.message_bus.subscribe("test_topic")
        try:
            res = q.get(timeout=0.1)
        except queue.Empty:
            res = None
        self.assertIsNone(res)

    def test_memory_reuse(self):
        # Run code agent
        job_state = {"job": {"id": "mem-1-abc"}, "pipeline_state": {}}
        t1 = AgentTask("mem", "CodeAgent", "Execute CodeAgent domain")
        self.coordinator.execute_plan([t1], job_state)
        
        # Check memory
        history = self.memory.recall_agent_strategy("CodeAgent")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].status, "success")
        self.assertEqual(history[0].task, "Execute CodeAgent domain")

    def test_conflicting_agent_output(self):
        job_state = {"job": {"id": "conflict-1-abc"}, "pipeline_state": {}}
        t1 = AgentTask("1", "AssetAgent", "test")
        t2 = AgentTask("2", "BlenderAgent", "test")
        t3 = AgentTask("3", "GodotAgent", "test")
        results = self.coordinator.execute_plan([t1, t2, t3], job_state)
        
        self.assertEqual(len(results), 3)
        status_set = set([r.status for r in results])
        self.assertEqual(status_set, {"success"})

if __name__ == "__main__":
    unittest.main()
