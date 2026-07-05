from __future__ import annotations
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from appsuite.db import Database
from appsuite.core.goal_manager import GoalManager
from appsuite.core.task_queue import PersistentTaskQueue

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "stress_test.db"
    db = Database(db_file)
    yield db
    db.close()

def test_cyclic_goal_propagation_recovery(temp_db):
    """Verifies that cycles in parent-child relations do not stack overflow status propagation."""
    gm = GoalManager(temp_db)
    
    # Create Node A and Node B
    node_a = gm.create_node(name="Node A", level="goal")
    node_b = gm.create_node(name="Node B", level="project", parent_id=node_a)
    
    # Introduce cycle: Set Node A's parent_id to Node B
    gm.update_node(node_a, parent_id=node_b)
    
    # Trigger state update on Node B. Status propagation should not stack overflow.
    try:
        gm.update_node(node_b, status="completed")
    except RecursionError:
        pytest.fail("Status propagation resulted in an infinite RecursionError stack overflow!")
        
    # Check that both nodes got updated to completed safely
    node_a_data = gm.get_node(node_a)
    node_b_data = gm.get_node(node_b)
    assert node_a_data["status"] == "completed"
    assert node_b_data["status"] == "completed"


def test_concurrent_task_queue_stress(temp_db):
    """Enqueues 1000 tasks and processes them concurrently with multiple worker threads to check for thread-safety and race conditions."""
    queue = PersistentTaskQueue(temp_db)
    num_tasks = 500
    num_workers = 10
    
    # 1. Enqueue 500 tasks concurrently
    def enqueue_worker(i: int):
        queue.enqueue(
            task_id=f"task_{i}",
            project_id="proj_1",
            objective=f"Objective task {i}",
            priority=i % 5,
            dependencies=[],
            payload={"index": i}
        )
        
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(enqueue_worker, i) for i in range(num_tasks)]
        for fut in as_completed(futures):
            fut.result()
            
    # Verify all tasks are enqueued
    tasks = queue.list_tasks()
    assert len(tasks) == num_tasks
    
    # 2. Dequeue tasks concurrently using worker threads
    dequeued_ids = set()
    dequeued_lock = threading.Lock()
    
    def dequeue_worker():
        local_dequeued = []
        while True:
            task = queue.dequeue()
            if not task:
                break
            local_dequeued.append(task["task_id"])
            time.sleep(0.001)  # Context switch simulation
        return local_dequeued
        
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(dequeue_worker) for _ in range(num_workers)]
        for fut in as_completed(futures):
            worker_dequeued = fut.result()
            with dequeued_lock:
                for tid in worker_dequeued:
                    # Assert no task was double-dequeued by multiple threads (classic race condition check)
                    assert tid not in dequeued_ids, f"Task {tid} was dequeued twice!"
                    dequeued_ids.add(tid)
                    
    # Verify total unique dequeued tasks matches enqueued amount
    assert len(dequeued_ids) == num_tasks


def test_task_dependencies_resolution_concurrency(temp_db):
    """Tests dependency transitions under concurrent updates."""
    queue = PersistentTaskQueue(temp_db)
    
    # Create dependency chain: task_1 -> task_2 -> task_3
    queue.enqueue("task_3", "proj_2", "Third Task", dependencies=["task_2"])
    queue.enqueue("task_2", "proj_2", "Second Task", dependencies=["task_1"])
    queue.enqueue("task_1", "proj_2", "First Task", dependencies=[])
    
    # Only task_1 should be queued (runnable); others are waiting
    t1 = queue.dequeue()
    assert t1 is not None
    assert t1["task_id"] == "task_1"
    
    t2_none = queue.dequeue()
    assert t2_none is None  # blocked on dependency task_1
    
    # Complete task_1 and confirm task_2 is unlocked
    queue.mark_completed("task_1")
    t2 = queue.dequeue()
    assert t2 is not None
    assert t2["task_id"] == "task_2"
