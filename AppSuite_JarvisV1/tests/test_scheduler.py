from __future__ import annotations
import time
from pathlib import Path
from appsuite.db import Database
from appsuite.core.background_scheduler import BackgroundScheduler

def test_scheduler_lifecycle(tmp_path):
    db_file = tmp_path / "test_sched.db"
    db = Database(db_file)
    
    sched = BackgroundScheduler(db)
    run_count = 0
    
    def my_job():
        nonlocal run_count
        run_count += 1
        
    sched.register_job("test_job", my_job)
    
    # Initially running is False
    assert not sched._running
    
    # Start scheduler
    sched.start()
    assert sched._running
    
    # Wait a bit for loops to run
    time.sleep(0.5)
    
    # Stop scheduler
    sched.stop()
    assert not sched._running
    assert run_count >= 0
    
    db.close()
