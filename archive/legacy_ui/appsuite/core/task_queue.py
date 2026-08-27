from __future__ import annotations
import json
import time
import threading
from typing import Any, Dict, List, Optional
from ..db import Database

class PersistentTaskQueue:
    """A thread-safe persistent priority queue supporting dependencies, retries, and pause/resume states."""
    
    def __init__(self, db: Database, event_bus: Optional[Any] = None) -> None:
        self.db = db
        self.event_bus = event_bus
        self._lock = threading.RLock()
        self._init_db()
        
    def _init_db(self) -> None:
        with self._lock:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS task_queue (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    priority INTEGER DEFAULT 1,
                    dependencies_json TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    retries INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    payload_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
        
    def enqueue(
        self,
        task_id: str,
        project_id: str,
        objective: str,
        priority: int = 1,
        dependencies: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> None:
        now = time.time()
        deps = dependencies or []
        payload_data = payload or {}
        
        # Determine initial status
        status = "waiting" if deps else "queued"
        
        with self._lock:
            self.db.execute(
                """
                INSERT OR REPLACE INTO task_queue
                (task_id, project_id, objective, priority, dependencies_json, status, retries, max_retries, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    task_id, project_id, objective, priority, json.dumps(deps),
                    status, max_retries, json.dumps(payload_data), now, now
                )
            )
        
        if self.event_bus:
            self.event_bus.publish("task_enqueued", {"task_id": task_id, "project_id": project_id})
            
    def dequeue(self) -> Optional[Dict[str, Any]]:
        """Pops and returns the highest priority runnable task (whose dependencies are all completed)."""
        with self._lock:
            self._update_waiting_tasks()
            
            # Get runnable tasks ordered by priority DESC (higher priority first) and created_at ASC
            rows = self.db.query(
                "SELECT * FROM task_queue WHERE status = 'queued' ORDER BY priority DESC, created_at ASC"
            )
            
            if not rows:
                return None
                
            task_row = rows[0]
            task_id = task_row["task_id"]
            
            # Update status to running
            self.db.execute(
                "UPDATE task_queue SET status = 'running', updated_at = ? WHERE task_id = ?",
                (time.time(), task_id)
            )
            
            task = dict(task_row)
            task["status"] = "running"
            task["payload"] = json.loads(task["payload_json"]) if task.get("payload_json") else {}
            task["dependencies"] = json.loads(task["dependencies_json"]) if task.get("dependencies_json") else []
            
            if self.event_bus:
                self.event_bus.publish("task_dequeued", {"task_id": task_id})
                
            return task
 
    def pause_task(self, task_id: str) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE task_queue SET status = 'paused', updated_at = ? WHERE task_id = ?",
                (time.time(), task_id)
            )
        if self.event_bus:
            self.event_bus.publish("task_paused", {"task_id": task_id})
 
    def resume_task(self, task_id: str) -> None:
        with self._lock:
            task = self.get_task(task_id)
            if not task:
                return
            
            deps = task.get("dependencies", [])
            status = "waiting" if deps else "queued"
            
            self.db.execute(
                "UPDATE task_queue SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, time.time(), task_id)
            )
        if self.event_bus:
            self.event_bus.publish("task_resumed", {"task_id": task_id})
            
    def cancel_task(self, task_id: str) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE task_queue SET status = 'cancelled', updated_at = ? WHERE task_id = ?",
                (time.time(), task_id)
            )
        if self.event_bus:
            self.event_bus.publish("task_cancelled", {"task_id": task_id})
 
    def change_priority(self, task_id: str, new_priority: int) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE task_queue SET priority = ?, updated_at = ? WHERE task_id = ?",
                (new_priority, time.time(), task_id)
            )
 
    def mark_completed(self, task_id: str) -> None:
        with self._lock:
            self.db.execute(
                "UPDATE task_queue SET status = 'completed', updated_at = ? WHERE task_id = ?",
                (time.time(), task_id)
            )
            if self.event_bus:
                self.event_bus.publish("task_completed", {"task_id": task_id})
            self._update_waiting_tasks()
 
    def mark_failed(self, task_id: str, retry_allowed: bool = True) -> bool:
        """Marks task failed. Returns True if task can be retried (enqueued again)."""
        with self._lock:
            row = self.db.query_one("SELECT * FROM task_queue WHERE task_id = ?", (task_id,))
            if not row:
                return False
                
            retries = row["retries"]
            max_retries = row["max_retries"]
            
            if retry_allowed and retries < max_retries:
                self.db.execute(
                    "UPDATE task_queue SET status = 'queued', retries = retries + 1, updated_at = ? WHERE task_id = ?",
                    (time.time(), task_id)
                )
                if self.event_bus:
                    self.event_bus.publish("task_retry", {"task_id": task_id, "retry_count": retries + 1})
                return True
            else:
                self.db.execute(
                    "UPDATE task_queue SET status = 'failed', updated_at = ? WHERE task_id = ?",
                    (time.time(), task_id)
                )
                if self.event_bus:
                    self.event_bus.publish("task_failed", {"task_id": task_id})
                return False
 
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.db.query_one("SELECT * FROM task_queue WHERE task_id = ?", (task_id,))
            if not row:
                return None
            task = dict(row)
            task["payload"] = json.loads(task["payload_json"]) if task.get("payload_json") else {}
            task["dependencies"] = json.loads(task["dependencies_json"]) if task.get("dependencies_json") else []
            return task
 
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if status:
                rows = self.db.query("SELECT * FROM task_queue WHERE status = ?", (status,))
            else:
                rows = self.db.query("SELECT * FROM task_queue")
                
            results = []
            for r in rows:
                task = dict(r)
                task["payload"] = json.loads(task["payload_json"]) if task.get("payload_json") else {}
                task["dependencies"] = json.loads(task["dependencies_json"]) if task.get("dependencies_json") else []
                results.append(task)
            return results
 
    def _update_waiting_tasks(self) -> None:
        """Transitions 'waiting' tasks to 'queued' once all their dependencies are completed."""
        with self._lock:
            rows = self.db.query("SELECT * FROM task_queue WHERE status = 'waiting'")
            for row in rows:
                deps = json.loads(row["dependencies_json"]) if row.get("dependencies_json") else []
                if not deps:
                    self.db.execute(
                        "UPDATE task_queue SET status = 'queued', updated_at = ? WHERE task_id = ?",
                        (time.time(), row["task_id"])
                    )
                    continue
                    
                # Check if all dependent task_ids are completed
                placeholders = ",".join("?" for _ in deps)
                completed_rows = self.db.query(
                    f"SELECT COUNT(*) as cnt FROM task_queue WHERE task_id IN ({placeholders}) AND status = 'completed'",
                    tuple(deps)
                )
                completed_count = completed_rows[0]["cnt"] if completed_rows else 0
                if completed_count == len(deps):
                    self.db.execute(
                        "UPDATE task_queue SET status = 'queued', updated_at = ? WHERE task_id = ?",
                        (time.time(), row["task_id"])
                    )
