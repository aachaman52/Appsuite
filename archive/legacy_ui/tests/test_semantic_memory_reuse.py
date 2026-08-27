from __future__ import annotations
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from appsuite.core.semantic_memory import SemanticMemory
from appsuite.core.jarvis_brain import JarvisBrain, ExecutionPlan
from appsuite.core.provider_manager import ProviderManager
from appsuite.core.token_banker import TokenBanker
from appsuite.core.hardware_manager import HardwareManager
from appsuite.core.jarvis import JarvisCore
from appsuite.db import Database

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_memory.db"
    db = Database(db_file)
    yield db
    db.close()

def test_semantic_strategy_reuse_and_avoidance(temp_db, tmp_path):
    # Set up mocks
    provider_mgr = ProviderManager([
        {"id": "nvidia-nim", "type": "llm", "name": "NIM", "model": "meta/llama-3.1-405b-instruct", "enabled": True}
    ])
    token_banker = TokenBanker({})
    hardware_mgr = HardwareManager({}, str(tmp_path))
    
    # 1. Initialize Semantic Memory & Brain
    memory = SemanticMemory(temp_db, provider_mgr)
    brain = JarvisBrain(memory, provider_mgr, token_banker, hardware_mgr, templates=None)
    
    # Pre-populate strategy memory with a successful run
    prompt = "Create a multiplayer FPS game with custom levels"
    strategy = {
        "template_id": "generic_scene",
        "reasoning": "Standard template execution",
        "agent_tasks": [
            {"task_id": "asset_1", "agent_type": "AssetAgent", "objective": "Download models"},
            {"task_id": "code_1", "agent_type": "CodeAgent", "objective": "Create logic", "dependencies": ["asset_1"]}
        ]
    }
    
    # Add strategy
    memory.strategy.add_strategy(prompt, strategy, outcome="success")
    
    # Mock get_similar_strategies to act as semantic matcher
    def mock_get_similar_strategies(query_prompt, limit=3, threshold=0.5):
        if "multiplayer" in query_prompt.lower():
            # If query is closely paraphrased (similarity score high)
            score = 0.95 if "custom levels" in query_prompt.lower() or "video game" in query_prompt.lower() else 0.70
            if score >= threshold:
                return [{
                    "id": "job123",
                    "prompt": prompt,
                    "strategy": strategy,
                    "outcome": "success",
                    "similarity_score": score
                }]
        elif "platformer" in query_prompt.lower():
            return [{
                "id": "job456",
                "prompt": "Create a retro platformer game",
                "strategy": {
                    "template_id": "godot_platformer",
                    "reasoning": "Failed execution attempt",
                    "agent_tasks": [
                        {"task_id": "asset_fail", "agent_type": "AssetAgent", "objective": "Search for fbx files"}
                    ]
                },
                "outcome": "failure",
                "similarity_score": 0.92
            }]
        return []

    with patch.object(memory.strategy, "get_similar_strategies", side_effect=mock_get_similar_strategies):
        # Test A: Reusing highly similar successful strategy directly without LLM
        # Query with exact prompt
        plan1 = brain.plan_execution(prompt)
        assert plan1 is not None
        assert plan1.metadata.get("memory_hit") is True
        assert plan1.template_id == "generic_scene"
        assert len(plan1.agent_tasks) == 2
        assert "strategy memory" in plan1.reasoning
        
        # Query with closely paraphrased prompt
        paraphrase = "Make a multiplayer FPS video game with custom levels"
        plan2 = brain.plan_execution(paraphrase)
        assert plan2 is not None
        assert plan2.metadata.get("memory_hit") is True
        assert plan2.template_id == "generic_scene"
        assert len(plan2.agent_tasks) == 2
        
        # Test B: In-context adaptation (similarity between 0.50 and 0.85)
        # Query with moderately similar prompt (triggers score = 0.70)
        moderate_prompt = "Build a cooperative multiplayer level shooter"
        
        # Mock LLM response to confirm it receives the reference example
        llm_mock = MagicMock(return_value='{"template_id": "medieval_village", "reasoning": "LLM adapted", "agent_tasks": []}')
        with patch.object(provider_mgr, "generate_text", llm_mock):
            plan3 = brain.plan_execution(moderate_prompt)
            assert plan3 is not None
            # Verify LLM was called since similarity is < 0.85
            assert llm_mock.called
            # Check system instruction contains reference example
            args, kwargs = llm_mock.call_args
            sys_inst = kwargs.get("system_instruction", "")
            assert "reference/inspiration" in sys_inst
            assert prompt in sys_inst

        # Test C: Avoid failed strategy paths
        fail_prompt = "Create a retro platformer game"
        llm_mock_avoid = MagicMock(return_value='{"template_id": "generic_scene", "reasoning": "Planned around failures", "agent_tasks": []}')
        with patch.object(provider_mgr, "generate_text", llm_mock_avoid):
            plan4 = brain.plan_execution(fail_prompt)
            assert plan4 is not None
            assert llm_mock_avoid.called
            args, kwargs = llm_mock_avoid.call_args
            sys_inst = kwargs.get("system_instruction", "")
            assert "Avoid reproducing the following past plans that FAILED" in sys_inst
            assert "asset_fail" in sys_inst


def test_remember_updates_strategy_outcome(temp_db, tmp_path):
    provider_mgr = ProviderManager([
        {"id": "nvidia-nim", "type": "llm", "name": "NIM", "model": "meta/llama-3.1-405b-instruct", "enabled": True}
    ])
    token_banker = TokenBanker({})
    hardware_mgr = HardwareManager({}, str(tmp_path))
    memory = SemanticMemory(temp_db, provider_mgr)
    brain = JarvisBrain(memory, provider_mgr, token_banker, hardware_mgr, templates=None)
    
    jarvis = JarvisCore({}, str(tmp_path))
    # Mock wiring
    jarvis.wire(
        db=temp_db,
        registry=MagicMock(),
        memory=memory,
        templates=MagicMock(),
        workers={},
        pipeline=MagicMock(),
        brain=brain,
        hardware=hardware_mgr,
        token_banker=token_banker
    )
    
    prompt = "Simple physics simulation"
    # Pre-populate strategy in strategy_memory
    strategy = {
        "template_id": "generic_scene",
        "reasoning": "Planned",
        "agent_tasks": []
    }
    memory.strategy.add_strategy(prompt, strategy, outcome="success")
    
    # 1. Verify it was added as success
    rows = temp_db.query("SELECT outcome FROM strategy_memory WHERE prompt = ?", (prompt,))
    assert len(rows) == 1
    assert rows[0]["outcome"] == "success"
    
    # 2. Call _remember with status="failed"
    plan = MagicMock()
    plan.template_id = "generic_scene"
    plan.scene_plan = {}
    plan.use_cached_assets = False
    plan.workers_to_run = []
    plan.reasons = []
    
    jarvis._remember("job123", prompt, plan, "failed", {})
    
    # 3. Verify strategy outcome was updated to failed
    rows_after = temp_db.query("SELECT outcome FROM strategy_memory WHERE prompt = ?", (prompt,))
    assert len(rows_after) == 1
    assert rows_after[0]["outcome"] == "failed"


def test_semantic_recall_benchmark(temp_db, tmp_path):
    provider_mgr = ProviderManager([])
    token_banker = TokenBanker({})
    hardware_mgr = HardwareManager({}, str(tmp_path))
    memory = SemanticMemory(temp_db, provider_mgr)
    brain = JarvisBrain(memory, provider_mgr, token_banker, hardware_mgr, templates=None)
    
    prompt = "Create medieval castle siege simulator"
    strategy = {
        "template_id": "generic_scene",
        "reasoning": "Test plan",
        "agent_tasks": []
    }
    
    # Store strategy
    memory.strategy.add_strategy(prompt, strategy, outcome="success")
    
    # Benchmark recall execution
    t0 = time.perf_counter()
    plan = brain.plan_execution(prompt)
    t_recall = time.perf_counter() - t0
    
    # Assert recall was super fast (usually < 0.05 seconds locally)
    assert plan.metadata.get("memory_hit") is True
    assert t_recall < 0.20
    print(f"\n[Benchmark] Semantic memory strategy recall took: {t_recall*1000.0:.3f}ms")
