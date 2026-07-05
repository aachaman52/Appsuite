from __future__ import annotations
import os
import pytest
from unittest.mock import MagicMock, patch
from appsuite.core.semantic_memory.embedding_client import EmbeddingClient
from appsuite.core.project_manager import ProjectManager, ProjectHierarchyNode
from appsuite.agents.base_agent import BaseAgent, AgentTask, AgentResult, ReflectionResult

class MockDB:
    def __init__(self):
        self.nodes = []
        self.embeddings = {}

    def get_cached_embedding(self, text):
        return self.embeddings.get(text)

    def cache_embedding(self, text, embedding):
        self.embeddings[text] = embedding

    def add_hierarchy_node(self, **kwargs):
        if "node_id" in kwargs:
            kwargs["id"] = kwargs["node_id"]
        self.nodes.append(kwargs)

    def get_project_hierarchy(self, project_id):
        return self.nodes

    def update_hierarchy_node_status(self, node_id, status):
        for n in self.nodes:
            if n["id"] == node_id:
                n["status"] = status
                break

    def query(self, q):
        if "strategy_memory" in q:
            return [{"prompt": "test_prompt", "strategy_json": "{}"}]
        elif "failure_memory" in q:
            return [{"prompt": "fail_prompt", "context_json": "{}"}]
        return []

class DummyAgent(BaseAgent):
    def plan(self, task: AgentTask, job_state: dict) -> list[str]:
        return ["step1"]

    def execute_tools(self, plan: list[str], job_state: dict) -> dict:
        if job_state.get("should_fail"):
            raise ValueError("Tool failure")
        return {"execution_results": [{"node1": "success"}], "assets": [{"role": "house", "file_path": "h.glb"}]}

# 1. Embedding Client tests
def test_embedding_client_fallback():
    client = EmbeddingClient(db=None)
    emb1 = client.get_embedding("medieval house")
    emb2 = client.get_embedding("house")
    emb3 = client.get_embedding("wooden barrel")
    
    assert len(emb1) == 512
    assert len(emb2) == 512
    
    sim1 = EmbeddingClient.cosine_similarity(emb1, emb2)
    sim2 = EmbeddingClient.cosine_similarity(emb1, emb3)
    
    # "medieval house" should be closer to "house" than "wooden barrel"
    # using our local bag-of-words character-level fallback
    assert sim1 > sim2

@patch("requests.post")
def test_embedding_client_api(mock_post):
    mock_post.return_value.json.return_value = {
        "data": [{"embedding": [0.1] * 512}]
    }
    mock_post.return_value.raise_for_status = MagicMock()
    
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "test_key"}):
        client = EmbeddingClient(db=None)
        emb = client.get_embedding("test goal")
        assert len(emb) == 512
        assert emb[0] == 0.1

# 2. Project Manager tests
def test_project_manager_planning():
    db = MockDB()
    pm = ProjectManager(db)
    
    # Medieval templates match
    plan = pm.create_project_plan("p1", "build a medieval village house")
    
    # Verify vision/project/milestones created
    node_types = [n["node_type"] for n in db.nodes]
    assert "vision" in node_types
    assert "project" in node_types
    assert "milestone" in node_types
    assert "task" in node_types
    
    # Verify task estimate duration
    tasks = [n for n in db.nodes if n["node_type"] == "task"]
    assert len(tasks) > 0
    assert tasks[0]["estimated_duration"] > 0.0

def test_project_manager_rescheduling():
    db = MockDB()
    pm = ProjectManager(db)
    
    # Create simple DAG
    # Node B depends on Node A
    db.add_hierarchy_node(node_id="A", project_id="p1", parent_id=None, node_type="task", status="pending", dependencies=[])
    db.add_hierarchy_node(node_id="B", project_id="p1", parent_id=None, node_type="task", status="pending", dependencies=["A"])
    
    # Mark A failed
    db.update_hierarchy_node_status("A", "failed")
    pm.dynamic_reschedule("p1", "A")
    pm.detect_blockers("p1")
    
    # B should be marked blocked
    node_b = next(n for n in db.nodes if n["id"] == "B")
    assert node_b["status"] == "blocked"

# 3. Agent Reflection & Repair tests
def test_agent_run_success():
    agent = DummyAgent("TestAgent", memory=MagicMock())
    task = AgentTask(task_id="t1", agent_type="TestAgent", objective="Build")
    job_state = {"should_fail": False}
    
    res = agent.run(task, job_state)
    assert res.status == "success"
    assert res.confidence == 1.0

def test_agent_run_repair_loop():
    agent = DummyAgent("AssetAgent", memory=MagicMock())
    task = AgentTask(task_id="t1", agent_type="AssetAgent", objective="Find houses")
    
    # Initially fail, but repair path broadens search terms and we execute success
    job_state = {"pipeline_state": {"assets": []}} # Empty assets triggers reflect gap
    
    with patch.object(agent, "execute_tools") as mock_exec:
        # Simulate state mutation and response
        def side_effect_fn(plan_arg, state_arg):
            if mock_exec.call_count == 1:
                state_arg["pipeline_state"]["assets"] = []
                return {"assets": []}
            else:
                state_arg["pipeline_state"]["assets"] = [{"role": "house", "file_path": "h.glb"}]
                return {"assets": [{"role": "house", "file_path": "h.glb"}]}
                
        mock_exec.side_effect = side_effect_fn
        
        res = agent.run(task, job_state)
        # Verify it ran execute_tools twice (initial + repaired)
        assert mock_exec.call_count == 2
        assert res.status == "success"
