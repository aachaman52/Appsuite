from __future__ import annotations
import json
import time
import uuid
import threading
from typing import Any, Dict, List, Optional
from ..db import Database

class GoalManager:
    """Manages long-term goals and object hierarchies (Visions -> Goals -> Projects ... -> Tasks)."""
    
    def __init__(self, db: Database, event_bus: Optional[Any] = None) -> None:
        self.db = db
        self.event_bus = event_bus
        self._lock = threading.RLock()
        self._init_db()
        
    def _init_db(self) -> None:
        with self._lock:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_hierarchy (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    level TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    priority INTEGER DEFAULT 1,
                    deadline REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    dependencies_json TEXT,
                    metadata_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
        
    def create_node(
        self,
        name: str,
        level: str,
        parent_id: Optional[str] = None,
        description: Optional[str] = None,
        priority: int = 1,
        deadline: Optional[float] = None,
        status: str = "pending",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None
    ) -> str:
        uid = node_id or str(uuid.uuid4())
        now = time.time()
        deps = dependencies or []
        meta = metadata or {}
        
        with self._lock:
            self.db.execute(
                """
                INSERT OR REPLACE INTO goal_hierarchy
                (id, parent_id, level, name, description, priority, deadline, status, dependencies_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid, parent_id, level, name, description, priority, deadline, status,
                    json.dumps(deps), json.dumps(meta), now, now
                )
            )
        
        if self.event_bus:
            self.event_bus.publish("goal_node_created", {"id": uid, "level": level, "name": name})
            
        return uid

    def update_node(self, node_id: str, _visited: Optional[set[str]] = None, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        
        # Serialize fields if needed
        if "dependencies" in fields:
            fields["dependencies_json"] = json.dumps(fields.pop("dependencies"))
        if "metadata" in fields:
            fields["metadata_json"] = json.dumps(fields.pop("metadata"))
            
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self.db.execute(
                f"UPDATE goal_hierarchy SET {cols} WHERE id = ?",
                (*fields.values(), node_id)
            )
            
            if self.event_bus:
                self.event_bus.publish("goal_node_updated", {"id": node_id, "updates": list(fields.keys())})
                
            # Dynamically evaluate parent state propagation
            node = self.get_node(node_id)
            if node and node.get("parent_id"):
                if _visited is None:
                    _visited = set()
                if node_id not in _visited:
                    _visited.add(node_id)
                    self._propagate_status(node["parent_id"], _visited=_visited)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.db.query_one("SELECT * FROM goal_hierarchy WHERE id = ?", (node_id,))
            if not row:
                return None
            return self._enrich_node(row)

    def _enrich_node(self, row: Dict[str, Any]) -> Dict[str, Any]:
        node = dict(row)
        if node.get("dependencies_json"):
            try:
                node["dependencies"] = json.loads(node["dependencies_json"])
            except Exception:
                node["dependencies"] = []
        else:
            node["dependencies"] = []
            
        if node.get("metadata_json"):
            try:
                node["metadata"] = json.loads(node["metadata_json"])
            except Exception:
                node["metadata"] = {}
        else:
            node["metadata"] = {}
        return node

    def list_nodes(self, level: Optional[str] = None, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM goal_hierarchy WHERE 1=1"
        params = []
        if level:
            sql += " AND level = ?"
            params.append(level)
        if parent_id:
            sql += " AND parent_id = ?"
            params.append(parent_id)
        elif parent_id is None and level == "vision":
            sql += " AND parent_id IS NULL"
            
        with self._lock:
            rows = self.db.query(sql, tuple(params))
            return [self._enrich_node(r) for r in rows]

    def delete_node(self, node_id: str) -> None:
        with self._lock:
            self.db.execute("DELETE FROM goal_hierarchy WHERE id = ?", (node_id,))
            # Recursively delete children
            children = self.list_nodes(parent_id=node_id)
            for child in children:
                self.delete_node(child["id"])

    def get_progress(self, node_id: str) -> float:
        """Returns the percentage of completed leaf-tasks/sub-nodes under this node."""
        with self._lock:
            children = self.list_nodes(parent_id=node_id)
            if not children:
                node = self.get_node(node_id)
                return 100.0 if node and node["status"] == "completed" else 0.0
                
            completed = 0
            total = len(children)
            for child in children:
                if child["status"] == "completed":
                    completed += 1
                else:
                    # Weighted contribution from sub-progress
                    completed += self.get_progress(child["id"]) / 100.0
            return (completed / total) * 100.0

    def _propagate_status(self, parent_id: str, _visited: Optional[set[str]] = None) -> None:
        with self._lock:
            children = self.list_nodes(parent_id=parent_id)
            if not children:
                return
                
            statuses = {c["status"] for c in children}
            
            # Propagation logic
            if all(s == "completed" for s in statuses):
                new_status = "completed"
            elif "failed" in statuses:
                new_status = "failed"
            elif "blocked" in statuses:
                new_status = "blocked"
            elif "running" in statuses:
                new_status = "running"
            else:
                new_status = "pending"
                
            parent = self.get_node(parent_id)
            if parent and parent["status"] != new_status:
                if _visited is None:
                    _visited = set()
                if parent_id not in _visited:
                    _visited.add(parent_id)
                    self.update_node(parent_id, _visited=_visited, status=new_status)

    def get_unfinished_nodes(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.db.query("SELECT * FROM goal_hierarchy WHERE status IN ('pending', 'running', 'blocked', 'paused')")
            return [self._enrich_node(r) for r in rows]
