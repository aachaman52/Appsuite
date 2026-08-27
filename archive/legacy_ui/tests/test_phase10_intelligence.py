from __future__ import annotations
import math
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from appsuite.agents.base_agent import BaseAgent, AgentTask, AgentPlan, AgentResult
from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.project_manager import ProjectManager, ProjectHierarchyNode
from appsuite.core.provider_manager import ProviderManager
from appsuite.db import Database

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)
    yield db
    db.close()

# 1. Test Mock Agent subclassing BaseAgent
class MockAgent(BaseAgent):
    def __init__(self, name: str, memory=None, workers=None):
        super().__init__(name, memory=memory, workers=workers)
        self.receive_called = False
        self.plan_called = False
        self.execute_called = False
        self.understand_called = False
        self.research_called = False
        self.reason_called = False
        self.verify_called = False
        self.learn_called = False
        self.optimize_called = False

    def understand(self, task, job_state):
        self.understand_called = True
        return super().understand(task, job_state)

    def research(self, task, understanding, job_state):
        self.research_called = True
        return super().research(task, understanding, job_state)

    def reason(self, task, research_data, job_state):
        self.reason_called = True
        return super().reason(task, research_data, job_state)

    def receive_task(self, task, job_state):
        self.receive_called = True

    def plan(self, task, job_state):
        self.plan_called = True
        return ["test_node"]

    def execute_tools(self, plan, job_state):
        self.execute_called = True
        return {"result": "ok"}

    def verify(self, task, result, job_state):
        self.verify_called = True
        return super().verify(task, result, job_state)

    def learn(self, task, result, job_state):
        self.learn_called = True
        return super().learn(task, result, job_state)

    def optimize(self, task, result, job_state):
        self.optimize_called = True
        return super().optimize(task, result, job_state)


def test_agent_10_step_cognitive_cycle():
    """Verify that all 10 stages of the cognitive cycle are executed in sequence."""
    memory_mock = MagicMock()
    agent = MockAgent("TestAgent", memory=memory_mock)
    task = AgentTask(task_id="t1", agent_type="mock", objective="Do test work")
    
    res = agent.run(task)
    
    assert res.status == "success"
    assert agent.understand_called
    assert agent.research_called
    assert agent.reason_called
    assert agent.receive_called
    assert agent.plan_called
    assert agent.execute_called
    assert agent.verify_called
    assert agent.learn_called
    assert agent.optimize_called


def test_dynamic_worker_routing():
    """Verify that worker selection is dynamically resolved."""
    agent = MockAgent("TestAgent")
    job_state = {}
    
    # Check default mappings
    assert agent.dynamic_route_worker("asset_search", job_state) == "internet"
    assert agent.dynamic_route_worker("blender_import", job_state) == "blender"
    assert agent.dynamic_route_worker("custom_node", job_state) == "custom_node"


def test_advanced_semantic_memory_episodic_decay(temp_db):
    """Verify episodic memory with exponential decay calculations."""
    memory = SemanticMemory(temp_db)
    
    # Store episodes
    memory.store_episode("job1", "Build FPS game", ["started", "compiled"], "success")
    time.sleep(0.01)
    memory.store_episode("job2", "Build RPG game", ["started", "failed"], "failed")
    
    # Recall episodes
    results = memory.recall_episodes("Build FPS game", limit=5)
    assert len(results) >= 2
    # The first result should have a high similarity score and ranking score
    assert results[0]["similarity_score"] > 0.8
    assert "decay_factor" in results[0]
    assert "ranking_score" in results[0]


def test_procedural_and_project_memory(temp_db):
    """Verify procedural memory recipes and project planning states."""
    memory = SemanticMemory(temp_db)
    
    # Procedural memory
    recipe = {"steps": ["find_prop", "optimize_fbx"]}
    memory.procedural.add_recipe("asset", recipe, "success")
    recipes = memory.procedural.get_recipes("asset")
    assert len(recipes) == 1
    assert recipes[0]["recipe"] == recipe

    # Project memory
    plan_state = {"nodes": ["n1", "n2"], "progress": 0.5}
    memory.store_project_state("proj_100", plan_state)
    recalled_state = memory.get_project_state("proj_100")
    assert recalled_state == plan_state


def test_memory_consolidation_and_compression(temp_db):
    """Verify memory consolidation/merging and compression/cleanup pipelines."""
    memory = SemanticMemory(temp_db)
    
    # Populate memory
    for i in range(110):
        # Insert raw entries directly into strategy memory
        temp_db.execute(
            "INSERT INTO strategy_memory (prompt, strategy_json, outcome, created_at) "
            "VALUES (?,?,?,?)",
            ("prompt", '{"worker": "internet"}', "success", time.time())
        )
    
    count_before = len(temp_db.query("SELECT * FROM strategy_memory"))
    assert count_before == 110
    
    # Consolidate
    memory.consolidate_memories()
    count_after = len(temp_db.query("SELECT * FROM strategy_memory"))
    # Highly redundant strategy rows should be consolidated/pruned
    assert count_after < 110


def test_autonomous_project_evolution_estimation(temp_db):
    """Verify ProjectManager's dynamic complexity and duration estimation."""
    pm = ProjectManager(temp_db)
    
    node = ProjectHierarchyNode(
        node_id="n1",
        project_id="p1",
        parent_id=None,
        node_type="task",
        name="Build multiplayer level save system",
        metadata={"agent": "godot"}
    )
    
    pm.estimate_complexity_and_duration(node)
    # Multiplayer and save keywords should boost duration and complexity
    assert node.estimated_duration > 15.0
    assert node.metadata["complexity"] == "high"


def test_project_manager_dynamic_reschedule(temp_db):
    """Verify that failure triggers dependency rescheduling to a recovery node."""
    pm = ProjectManager(temp_db)
    
    project_id = "proj_test_99"
    # Create hierarchy in DB
    temp_db.add_hierarchy_node("n_src", project_id, None, "task", "Source assets", "failed", metadata={"agent": "asset"})
    temp_db.add_hierarchy_node("n_opt", project_id, None, "task", "Optimize assets", "pending", dependencies=["n_src"], metadata={"agent": "blender"})
    
    # Reschedule failed source node
    pm.dynamic_reschedule(project_id, "n_src")
    
    # Check that "n_opt" now depends on a recovery node instead of the failed "n_src"
    nodes = temp_db.get_project_hierarchy(project_id)
    n_opt_updated = next(n for n in nodes if n["id"] == "n_opt")
    dependencies = n_opt_updated["dependencies"]
    
    assert "n_src" not in dependencies
    assert any(d.startswith("recovery_") for d in dependencies)
    # The downstream node status should reset to pending for execution
    assert n_opt_updated["status"] == "pending"


def test_provider_intelligence_quality_latency():
    """Verify ProviderManager's latency tracking, quality estimation, and sorting."""
    providers = [
        {"id": "prov_high_q", "type": "llm", "name": "Sonnet", "model": "claude-3-5-sonnet-20240620", "enabled": True},
        {"id": "prov_low_q", "type": "llm", "name": "Haiku", "model": "claude-3-haiku-20240307", "enabled": True}
    ]
    pm = ProviderManager(providers)
    
    assert pm.estimate_model_quality("claude-3-5-sonnet-20240620") == 0.96
    assert pm.estimate_model_quality("claude-3-haiku-20240307") == 0.65
    
    # Latency tracking
    pm.latency_history["prov_high_q"] = [1.2, 1.4, 1.3]
    assert pm.estimate_model_latency("prov_high_q") == pytest.approx(1.3)
