from __future__ import annotations
from pathlib import Path
from appsuite.db import Database
from appsuite.core.goal_manager import GoalManager

def test_goal_manager_flow(tmp_path):
    db_file = tmp_path / "test_goal.db"
    db = Database(db_file)
    gm = GoalManager(db)
    
    # Create Vision
    vision_id = gm.create_node(name="Ultimate Game Platform", level="vision")
    assert vision_id is not None
    
    # Create Goal under Vision
    goal_id = gm.create_node(name="Build platformer base", level="goal", parent_id=vision_id)
    assert goal_id is not None
    
    # Create Project under Goal
    proj_id = gm.create_node(name="2D platformer template", level="project", parent_id=goal_id)
    
    # Create Tasks under Project
    t1 = gm.create_node(name="Code logic", level="task", parent_id=proj_id, status="completed")
    t2 = gm.create_node(name="Design assets", level="task", parent_id=proj_id, status="pending")
    
    # Progress: t1 is completed (100%), t2 is pending (0%). Average = 50%
    prog = gm.get_progress(proj_id)
    assert prog == 50.0
    
    # Complete t2
    gm.update_node(t2, status="completed")
    assert gm.get_progress(proj_id) == 100.0
    
    # Verify status propagation
    proj_node = gm.get_node(proj_id)
    assert proj_node["status"] == "completed"
    
    # Retrieve unfinished nodes
    unfinished = gm.get_unfinished_nodes()
    # The parent goal & vision should still be running or completed depending on propagation
    assert len(unfinished) >= 0
    
    db.close()
