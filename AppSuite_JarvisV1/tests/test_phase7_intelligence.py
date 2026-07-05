"""Unit tests for Phase 7: LLM Intelligence Layer."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from appsuite.db import Database
from appsuite.core.provider_manager import ProviderManager
from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.jarvis import JarvisCore, JarvisPlan
from appsuite.core.jarvis_brain import JarvisBrain, ExecutionPlan
from appsuite.engine.langgraph_agent import StateGraph
from appsuite.agents.base_agent import AgentTask


class TestStateGraph(unittest.TestCase):
    def test_basic_graph_execution(self):
        graph = StateGraph()
        
        def step_1(state):
            state["val"] = state.get("val", 0) + 1
            return state
            
        def step_2(state):
            state["val"] += 2
            return state
            
        graph.add_node("s1", step_1)
        graph.add_node("s2", step_2)
        graph.set_entry_point("s1")
        graph.add_edge("s1", "s2")
        
        compiled = graph.compile()
        res = compiled.invoke({"val": 0})
        self.assertEqual(res["val"], 3)
        self.assertEqual(res["_graph_path"], ["s1", "s2", "__end__"])

    def test_conditional_graph_execution(self):
        graph = StateGraph()
        
        def start_node(state):
            state["val"] = 10
            return state
            
        def decider_node(state):
            return state
            
        def route_fn(state):
            return "high" if state["val"] > 5 else "low"
            
        def high_node(state):
            state["route"] = "high_path"
            return state
            
        def low_node(state):
            state["route"] = "low_path"
            return state
            
        graph.add_node("start", start_node)
        graph.add_node("decider", decider_node)
        graph.add_node("high", high_node)
        graph.add_node("low", low_node)
        
        graph.set_entry_point("start")
        graph.add_edge("start", "decider")
        graph.add_conditional_edges("decider", route_fn, {"high": "high", "low": "low"})
        
        compiled = graph.compile()
        res = compiled.invoke({"val": 0})
        self.assertEqual(res["route"], "high_path")
        self.assertEqual(res["_graph_path"], ["start", "decider", "high", "__end__"])

    def test_loop_prevention(self):
        graph = StateGraph()
        def looping_node(state):
            return state
        graph.add_node("loop", looping_node)
        graph.set_entry_point("loop")
        graph.add_edge("loop", "loop")
        
        compiled = graph.compile()
        res = compiled.invoke({})
        # The loop count safety breaker stops infinite execution
        self.assertLess(len(res["_graph_path"]), 52)


class TestPersistentMemory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_file = self.temp_dir / "test_memory.db"
        self.db = Database(self.db_file)
        self.memory = SemanticMemory(self.db)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_failure_memory_sqlite_roundtrip(self):
        self.memory.failure.log_failure("medieval village", "Blender import error", {"node": "blender"})
        failures = self.memory.failure.get_failures_for_prompt("medieval village")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["error"], "Blender import error")
        self.assertEqual(failures[0]["context"]["node"], "blender")

    def test_strategy_memory_sqlite_roundtrip(self):
        strat = {"tasks": ["task1", "task2"], "template": "village"}
        self.memory.strategy.add_strategy("medieval village", strat, "success")
        strategies = self.memory.strategy.get_strategies_for_prompt("medieval village")
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0]["strategy"]["template"], "village")


class TestIntelligentPlanner(unittest.TestCase):
    def setUp(self):
        os.environ["MOCK_KEY"] = "mock_key_value"

    def tearDown(self):
        if "MOCK_KEY" in os.environ:
            del os.environ["MOCK_KEY"]

    def test_planner_llm_parsing_and_fallback(self):
        mock_provider = MagicMock()
        # Invalid JSON initially, then valid JSON on self-correction retry
        mock_provider.generate_text.side_effect = [
            "NOT_JSON_RESPONSE",
            json.dumps({
                "template_id": "medieval_village",
                "reasoning": "LLM successfully planned",
                "needed_assets": [
                    {"role": "house", "count": 2, "search_terms": ["house"], "required": True}
                ],
                "agent_tasks": [
                    {"task_id": "asset_1", "agent_type": "AssetAgent", "objective": "Get house", "dependencies": [], "priority": 1}
                ]
            })
        ]
        
        manager = ProviderManager([
            {"id": "mock_llm", "type": "llm", "enabled": True, "api_key_env": "MOCK_KEY"}
        ])
        # Inject the mock provider call
        manager._call_provider_api = lambda p, pr, s, t, **k: (mock_provider.generate_text(), 10, 20)
        
        memory = MagicMock()
        memory.failure.get_failures_for_prompt.return_value = []
        hardware = MagicMock()
        hardware.resources.return_value = {"ram_percent": 10.0}
        
        brain = JarvisBrain(memory, manager, MagicMock(), hardware, MagicMock())
        plan = brain.plan_execution("medieval village")
        
        self.assertEqual(plan.metadata.get("llm_planned"), True)
        self.assertEqual(plan.reasoning, "LLM successfully planned")
        self.assertEqual(len(plan.agent_tasks), 1)
        self.assertEqual(plan.agent_tasks[0].agent_type, "AssetAgent")


class TestProviderFailover(unittest.TestCase):
    def setUp(self):
        os.environ["KEY_1"] = "val1"
        os.environ["KEY_2"] = "val2"

    def tearDown(self):
        if "KEY_1" in os.environ:
            del os.environ["KEY_1"]
        if "KEY_2" in os.environ:
            del os.environ["KEY_2"]

    def test_failover_limits_and_acquisition(self):
        providers = [
            {
                "id": "nim_1",
                "name": "NIM 1",
                "type": "llm",
                "base_url": "https://nim1.api.com",
                "api_key_env": "KEY_1",
                "enabled": True,
                "priority": 1
            },
            {
                "id": "nim_2",
                "name": "NIM 2",
                "type": "llm",
                "base_url": "https://nim2.api.com",
                "api_key_env": "KEY_2",
                "enabled": True,
                "priority": 2
            }
        ]
        
        manager = ProviderManager(providers)
        
        # Simulated failures on nim_1
        for _ in range(3):
            manager.report_failure("nim_1")
            
        # Acquiring should automatically select nim_2 due to cooldown
        candidates = manager.providers_for("llm")
        active_candidates = [c for c in candidates if manager._failures.get(c["id"], 0) < 3]
        self.assertEqual(active_candidates[0]["id"], "nim_2")


class TestDynamicReplanning(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.db_file = self.temp_dir / "test_replan.db"
        self.db = Database(self.db_file)
        self.memory = SemanticMemory(self.db)
        
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_reflection_and_replanning_loop(self):
        # Setup a simulated plan
        t1 = AgentTask("asset_1", "AssetAgent", "find asset")
        plan = JarvisPlan(
            prompt="medieval village",
            template_id="medieval_village",
            agent_tasks=[t1],
            reasons=[]
        )
        
        # Mock supervisor & pipelines
        class MockPipeline:
            def __init__(self):
                self.output_dir = "."
            def execute(self, job):
                return {}
                
        class MockBrain:
            def __init__(self):
                self.replan_called = False
            def plan_execution(self, prompt, template_id=None):
                if "failed" in prompt:
                    self.replan_called = True
                    # Return alternative plan that succeeds
                    t2 = AgentTask("repair_code", "CodeAgent", "repair files")
                    return ExecutionPlan(
                        stages=["output_validation"],
                        agent_tasks=[t2],
                        reasoning="Repaired plan after failure"
                    )
                return ExecutionPlan(stages=[], agent_tasks=[])
                
        # Mock Coordinator
        class MockCoordinator:
            def __init__(self):
                self.attempts = 0
            def execute_plan(self, tasks, job_state):
                self.attempts += 1
                class TaskResult:
                    def __init__(self, tid, name, status, err=""):
                        self.task_id = tid
                        self.agent_name = name
                        self.status = status
                        self.output = {"error": err}
                # First run fails, second succeeds
                if self.attempts == 1:
                    return [TaskResult("asset_1", "AssetAgent", "failed", "Simulated Blender Crash")]
                else:
                    return [TaskResult("repair_code", "CodeAgent", "success")]

        jarvis = JarvisCore({"max_attempts": 2, "backoff_seconds": 0.01}, ".")
        jarvis._pipeline = MockPipeline()
        jarvis._templates = MagicMock()
        jarvis._templates.resolve.return_value = {"id": "medieval_village"}
        jarvis._memory = self.memory
        jarvis._brain = MockBrain()
        jarvis._coordinator = MockCoordinator()
        
        # Diagnostic list to record reasoning steps (Human Override)
        diagnostics = []
        jarvis.on_reasoning_step = lambda step: diagnostics.append(step)
        
        res = jarvis._execute_pipeline({"id": "job123", "prompt": "medieval village"}, plan)
        
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["agent_results"]), 1)
        self.assertEqual(res["agent_results"][0]["task_id"], "repair_code")
        self.assertTrue(jarvis._brain.replan_called)
        
        # Verify diagnostics recorded (Human Override verification)
        self.assertEqual(len(diagnostics), 2) # reflect step 1, reflect step 2
        self.assertEqual(diagnostics[0]["failed_tasks"], ["asset_1"])
        
        # Verify failure got persisted to memory
        failures = self.memory.failure.get_failures_for_prompt("medieval village")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["error"], "Simulated Blender Crash")


if __name__ == "__main__":
    unittest.main()
