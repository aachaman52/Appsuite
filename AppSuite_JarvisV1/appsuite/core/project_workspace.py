from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..db import Database

class ProjectWorkspaceManager:
    """Manages simultaneous projects, registry of workspaces, resource limits, and isolated project directory structures."""
    
    def __init__(self, db: Database, base_workspace_dir: Path, event_bus: Optional[Any] = None) -> None:
        self.db = db
        self.base_workspace_dir = Path(base_workspace_dir)
        self.event_bus = event_bus
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects_registry (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                root_path TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                dependencies_json TEXT,
                resources_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        
    def register_project(
        self,
        project_id: str,
        name: str,
        priority: int = 1,
        dependencies: Optional[List[str]] = None,
        resources: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        now = time.time()
        deps = dependencies or []
        res = resources or {"max_cpu": 100.0, "max_memory_mb": 1024}
        
        # Ensure completely isolated filesystem output directory for project
        project_dir = self.base_workspace_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        root_path = str(project_dir.resolve())
        
        self.db.execute(
            """
            INSERT OR REPLACE INTO projects_registry
            (project_id, name, root_path, priority, status, dependencies_json, resources_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (project_id, name, root_path, priority, json.dumps(deps), json.dumps(res), now, now)
        )
        
        project_data = {
            "project_id": project_id,
            "name": name,
            "root_path": root_path,
            "priority": priority,
            "status": "pending",
            "dependencies": deps,
            "resources": res,
            "created_at": now,
            "updated_at": now
        }
        
        if self.event_bus:
            self.event_bus.publish("project_registered", project_data)
            
        return project_data

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.query_one("SELECT * FROM projects_registry WHERE project_id = ?", (project_id,))
        if not row:
            return None
        return self._enrich_project(row)

    def update_project_status(self, project_id: str, status: str) -> None:
        self.db.execute(
            "UPDATE projects_registry SET status = ?, updated_at = ? WHERE project_id = ?",
            (status, time.time(), project_id)
        )
        if self.event_bus:
            self.event_bus.publish("project_status_changed", {"project_id": project_id, "status": status})

    def list_projects(self) -> List[Dict[str, Any]]:
        rows = self.db.query("SELECT * FROM projects_registry ORDER BY priority DESC, created_at ASC")
        return [self._enrich_project(r) for r in rows]

    def _enrich_project(self, row: Dict[str, Any]) -> Dict[str, Any]:
        p = dict(row)
        p["dependencies"] = json.loads(p["dependencies_json"]) if p.get("dependencies_json") else []
        p["resources"] = json.loads(p["resources_json"]) if p.get("resources_json") else {}
        return p

    def get_execution_order(self) -> List[str]:
        """Resolves dependencies and outputs project topological sorting order."""
        projects = self.list_projects()
        adj: Dict[str, List[str]] = {p["project_id"]: p["dependencies"] for p in projects}
        
        visited = set()
        temp = set()
        order = []
        
        def visit(node: str):
            if node in temp:
                # Cycle detected, break it or skip
                return
            if node not in visited:
                temp.add(node)
                for neighbor in adj.get(node, []):
                    if neighbor in adj: # only resolve registered projects
                        visit(neighbor)
                temp.remove(node)
                visited.add(node)
                order.append(node)
                
        for pid in adj:
            if pid not in visited:
                visit(pid)
                
        return order
