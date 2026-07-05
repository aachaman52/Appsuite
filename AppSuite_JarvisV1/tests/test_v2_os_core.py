from __future__ import annotations
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from appsuite.agents.coordinator import AgentCoordinator
from appsuite.agents.message_bus import MessageBus
from appsuite.agents.base_agent import AgentTask
from appsuite.core.jarvis_brain import ExecutionPlan
from appsuite.core.project_manager import ProjectManager, ProjectHierarchyNode
from appsuite.core.vision import VisionSubsystem
from appsuite.workers.validation_worker import ValidationWorker
from appsuite.core.state import WorkerStatus

def test_v2_multi_agent_debate():
    message_bus = MessageBus()
    coordinator = AgentCoordinator(message_bus=message_bus)
    
    t1 = AgentTask(task_id="task_1", agent_type="GodotAgent", objective="Build test screen", priority=3)
    initial_plan = [t1]
    
    # Run the debate room
    debated_plan = coordinator.debate_plan("Build FPS game", initial_plan)
    
    assert len(debated_plan) == 1
    # Check that priority has been modified due to disagreement and planner revisions
    assert debated_plan[0].priority == 2
    assert debated_plan[0].metadata.get("revised_in_debate") is True

def test_v2_advanced_planning_fields():
    # Instantiate ExecutionPlan with V2 estimation properties
    plan = ExecutionPlan(
        stages=["asset_search", "godot_import"],
        reasoning="Simple test plan",
        alternative_stages=["fallback_assets"],
        estimated_cost_usd=0.04,
        estimated_duration_seconds=95.0,
        probabilistic_success_rate=0.97
    )
    
    plan_dict = plan.to_dict()
    assert plan_dict["estimated_cost_usd"] == 0.04
    assert plan_dict["estimated_duration_seconds"] == 95.0
    assert plan_dict["probabilistic_success_rate"] == 0.97
    assert plan_dict["alternative_stages"] == ["fallback_assets"]

def test_v2_checkpoint_save_and_restore():
    # Setup database Mock
    db = MagicMock()
    stored_checkpoint = {}
    
    def mock_execute(sql, params=()):
        if "INSERT OR REPLACE" in sql:
            stored_checkpoint["value_json"] = params[1]
            
    def mock_query_one(sql, params=()):
        if "SELECT value_json" in sql:
            return stored_checkpoint
        return None
        
    db.execute.side_effect = mock_execute
    db.query_one.side_effect = mock_query_one
    
    pm = ProjectManager(db)
    checkpoint_state = {"pipeline_state": {"test_val": 42}, "attempt": 1, "agent_tasks": []}
    
    pm.save_checkpoint("proj_123", checkpoint_state)
    loaded = pm.load_checkpoint("proj_123")
    
    assert loaded is not None
    assert loaded["pipeline_state"]["test_val"] == 42
    assert loaded["attempt"] == 1

def test_v2_vision_inspections():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        screenshot = tmp_path / "screenshot.png"
        baseline = tmp_path / "baseline.png"
        
        vision = VisionSubsystem()
        # UI Inspection
        res = vision.inspect_ui_layout(screenshot, ["player", "enemy"])
        assert res["overlaps_detected"] is False  # Bounding boxes do not overlap
        assert len(res["elements_found"]) > 0
        
        # Scene compare
        compare_res = vision.compare_rendered_scenes(screenshot, baseline)
        assert compare_res["ssim_score"] == 0.98
        assert compare_res["regression_detected"] is False
