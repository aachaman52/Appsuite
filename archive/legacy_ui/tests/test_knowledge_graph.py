from __future__ import annotations
from pathlib import Path
from appsuite.db import Database
from appsuite.core.knowledge_graph import KnowledgeGraph

def test_knowledge_graph_flow(tmp_path):
    db_file = tmp_path / "test_kg.db"
    db = Database(db_file)
    kg = KnowledgeGraph(db)
    
    # Register entities
    kg.add_node("proj_1", "Platformer Project", "project", {"priority": "high"})
    kg.add_node("asset_1", "Hero Sprite", "asset", {"format": "png"})
    kg.add_node("scene_1", "Main Menu Scene", "scene")
    
    # Establish relations
    kg.add_edge("proj_1", "scene_1", "requires")
    kg.add_edge("scene_1", "asset_1", "depends_on")
    
    # Dependency lookup
    deps = kg.find_dependencies("proj_1")
    assert "scene_1" in deps
    assert "asset_1" in deps
    
    # Impact Analysis (If asset_1 changes, what is impacted?)
    impacted = kg.impact_analysis("asset_1")
    assert "scene_1" in impacted
    assert "proj_1" in impacted
    
    # Traversal
    subgraph = kg.traverse("proj_1", max_depth=2)
    assert len(subgraph["nodes"]) == 3
    assert len(subgraph["edges"]) == 2
    
    db.close()
