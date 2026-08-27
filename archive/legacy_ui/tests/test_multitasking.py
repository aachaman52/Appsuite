from __future__ import annotations
from pathlib import Path
from appsuite.db import Database
from appsuite.core.project_workspace import ProjectWorkspaceManager

def test_multitasking_workspaces(tmp_path):
    db_file = tmp_path / "test_multi.db"
    db = Database(db_file)
    wm = ProjectWorkspaceManager(db, tmp_path / "workspaces")
    
    # Register multiple projects
    wm.register_project("p_core", "Core assets library", priority=3)
    wm.register_project("p_game", "Drift racer gameplay", priority=2, dependencies=["p_core"])
    wm.register_project("p_ui", "Speedometer HUD overlay", priority=1, dependencies=["p_core", "p_game"])
    
    # Assert directories are isolated
    core_dir = tmp_path / "workspaces" / "p_core"
    game_dir = tmp_path / "workspaces" / "p_game"
    assert core_dir.exists()
    assert game_dir.exists()
    
    # Assert topological sorting
    order = wm.get_execution_order()
    assert order.index("p_core") < order.index("p_game")
    assert order.index("p_game") < order.index("p_ui")
    
    # Verify priority listing
    projects = wm.list_projects()
    assert projects[0]["project_id"] == "p_core"
    
    db.close()
