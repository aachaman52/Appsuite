from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from ..db import Database

class KnowledgeGraph:
    """Manages relationships and entities across projects, assets, code, APIs, and agents using persistent storage."""
    
    def __init__(self, db: Database, event_bus: Optional[Any] = None) -> None:
        self.db = db
        self.event_bus = event_bus
        self._init_db()
        
    def _init_db(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                type TEXT NOT NULL,
                properties_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                properties_json TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (source_id) REFERENCES kg_nodes(id),
                FOREIGN KEY (target_id) REFERENCES kg_nodes(id),
                UNIQUE(source_id, target_id, relation_type)
            );
            """
        )
        
    def add_node(self, node_id: str, label: str, node_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        now = time.time()
        props = properties or {}
        self.db.execute(
            """
            INSERT OR REPLACE INTO kg_nodes (id, label, type, properties_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (node_id, label, node_type, json.dumps(props), now, now)
        )
        if self.event_bus:
            self.event_bus.publish("kg_node_added", {"id": node_id, "type": node_type})
            
    def add_edge(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        edge_id = f"{source_id}->{relation_type}->{target_id}"
        now = time.time()
        props = properties or {}
        
        # Verify nodes exist, if not create dummy placeholder nodes
        if not self.get_node(source_id):
            self.add_node(source_id, source_id, "placeholder")
        if not self.get_node(target_id):
            self.add_node(target_id, target_id, "placeholder")
            
        self.db.execute(
            """
            INSERT OR REPLACE INTO kg_edges (id, source_id, target_id, relation_type, properties_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (edge_id, source_id, target_id, relation_type, json.dumps(props), now)
        )
        if self.event_bus:
            self.event_bus.publish("kg_edge_added", {"source": source_id, "target": target_id, "relation": relation_type})

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.query_one("SELECT * FROM kg_nodes WHERE id = ?", (node_id,))
        if not row:
            return None
        node = dict(row)
        node["properties"] = json.loads(node["properties_json"]) if node.get("properties_json") else {}
        return node

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Tuple[Dict[str, Any], str]]:
        """Returns neighbor nodes and relation types connected to the node."""
        neighbors = []
        
        if direction in ("out", "both"):
            rows = self.db.query(
                "SELECT n.*, e.relation_type FROM kg_nodes n JOIN kg_edges e ON n.id = e.target_id WHERE e.source_id = ?",
                (node_id,)
            )
            for r in rows:
                neighbors.append((self._enrich_node(r), r["relation_type"]))
                
        if direction in ("in", "both"):
            rows = self.db.query(
                "SELECT n.*, e.relation_type FROM kg_nodes n JOIN kg_edges e ON n.id = e.source_id WHERE e.target_id = ?",
                (node_id,)
            )
            for r in rows:
                neighbors.append((self._enrich_node(r), r["relation_type"]))
                
        return neighbors

    def _enrich_node(self, row: Dict[str, Any]) -> Dict[str, Any]:
        node = dict(row)
        node["properties"] = json.loads(node["properties_json"]) if node.get("properties_json") else {}
        return node

    def traverse(self, start_node_id: str, max_depth: int = 3) -> Dict[str, Any]:
        """Performs Breadth-First Search traversal to list connected subgraph components."""
        visited_nodes: Dict[str, Dict[str, Any]] = {}
        visited_edges: List[Dict[str, Any]] = []
        
        start_node = self.get_node(start_node_id)
        if not start_node:
            return {"nodes": [], "edges": []}
            
        queue: List[Tuple[str, int]] = [(start_node_id, 0)]
        visited_nodes[start_node_id] = start_node
        
        while queue:
            node_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue
                
            # Get outgoing edges
            out_edges = self.db.query("SELECT * FROM kg_edges WHERE source_id = ?", (node_id,))
            for e in out_edges:
                t_id = e["target_id"]
                if t_id not in visited_nodes:
                    node = self.get_node(t_id)
                    if node:
                        visited_nodes[t_id] = node
                        queue.append((t_id, depth + 1))
                visited_edges.append({
                    "source": node_id,
                    "target": t_id,
                    "relation": e["relation_type"],
                    "properties": json.loads(e["properties_json"]) if e.get("properties_json") else {}
                })
                
        return {
            "nodes": list(visited_nodes.values()),
            "edges": visited_edges
        }

    def find_dependencies(self, node_id: str) -> List[str]:
        """Recursively resolves dependencies of a node (relation types like 'depends_on' or 'requires')."""
        dependencies = set()
        to_visit = [node_id]
        
        while to_visit:
            curr = to_visit.pop(0)
            rows = self.db.query(
                "SELECT target_id FROM kg_edges WHERE source_id = ? AND relation_type IN ('depends_on', 'requires', 'uses')",
                (curr,)
            )
            for r in rows:
                dep_id = r["target_id"]
                if dep_id not in dependencies:
                    dependencies.add(dep_id)
                    to_visit.append(dep_id)
                    
        return list(dependencies)

    def impact_analysis(self, changed_node_id: str) -> List[str]:
        """Calculates what nodes are impacted if this node is modified (transitive backward relation)."""
        impacted = set()
        to_visit = [changed_node_id]
        
        while to_visit:
            curr = to_visit.pop(0)
            # Find nodes that depend on curr
            rows = self.db.query(
                "SELECT source_id FROM kg_edges WHERE target_id = ? AND relation_type IN ('depends_on', 'requires', 'uses')",
                (curr,)
            )
            for r in rows:
                imp_id = r["source_id"]
                if imp_id not in impacted:
                    impacted.add(imp_id)
                    to_visit.append(imp_id)
                    
        return list(impacted)
