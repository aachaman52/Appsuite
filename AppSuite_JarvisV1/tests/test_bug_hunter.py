from __future__ import annotations
from pathlib import Path
from appsuite.db import Database
from appsuite.core.bug_hunter import AutonomousBugHunter

def test_bug_hunter_cycle(tmp_path):
    db_file = tmp_path / "test_bh.db"
    db = Database(db_file)
    bh = AutonomousBugHunter(db, tmp_path)
    
    # Pre-populate failure memory
    db.add_failure_memory(
        prompt="Synthesize 3d character mesh",
        error="RuntimeError: Connection timed out calling provider API",
        context={"file_path": "appsuite/workers/blender_worker.py"}
    )
    
    # Run loop
    report = bh.run_bug_hunting_cycle()
    assert report is not None
    assert report["status"] == "accepted"
    assert report["regression_status"] == "no_regression"
    assert "timeout" in report["root_cause"].lower()
    assert report["files_changed"] == ["appsuite/workers/blender_worker.py"]
    assert report["confidence_score"] >= 0.70
    
    db.close()
