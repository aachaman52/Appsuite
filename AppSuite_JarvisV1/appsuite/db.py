"""SQLite database layer: schema definition and thread-safe access."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT,
    progress REAL NOT NULL DEFAULT 0.0,
    template_id TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    result_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    stage TEXT,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    role TEXT,
    name TEXT,
    source TEXT,
    source_url TEXT,
    file_path TEXT,
    file_hash TEXT,
    file_size INTEGER,
    format TEXT,
    quality_score REAL,
    metadata_json TEXT,
    dependencies_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    prompt TEXT,
    template_id TEXT,
    outcome TEXT,
    summary_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS failure_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT,
    error TEXT,
    context_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT,
    strategy_json TEXT,
    outcome TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS world_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT,
    updated_at REAL NOT NULL,
    UNIQUE(job_id, key)
);

CREATE TABLE IF NOT EXISTS project_hierarchy (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    parent_id TEXT,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    estimated_duration REAL DEFAULT 0.0,
    actual_duration REAL DEFAULT 0.0,
    dependencies_json TEXT,
    metadata_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS embeddings_cache (
    text_hash TEXT PRIMARY KEY,
    text_content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS procedural_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT,
    recipe_json TEXT,
    outcome TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS success_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    template_id TEXT,
    workers_used_json TEXT,
    assets_used_json TEXT,
    completion_time_secs REAL,
    generated_files_json TEXT,
    reliability_score REAL DEFAULT 1.0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name TEXT NOT NULL,
    asset_source TEXT NOT NULL,
    category TEXT,
    use_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 1,
    fail_count INTEGER DEFAULT 0,
    import_issues_json TEXT,
    last_used_at REAL NOT NULL,
    UNIQUE(asset_name, asset_source)
);

CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(file_hash);
CREATE INDEX IF NOT EXISTS idx_success_mem_prompt ON success_memory(prompt);
CREATE INDEX IF NOT EXISTS idx_asset_mem_category ON asset_memory(category);
"""


class Database:
    def __init__(self, path: Path):
        self.path = str(path)
        self._local = threading.local()
        self._connections: set[sqlite3.Connection] = set()
        self._lock = threading.RLock()
        
        # Init schema and database in WAL mode using a temporary connection
        conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()
        self._closed = False

    def _get_conn(self) -> sqlite3.Connection:
        with self._lock:
            if self._closed:
                raise RuntimeError("Database connection is closed.")
            if not hasattr(self._local, "conn"):
                conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL;")
                self._local.conn = conn
                self._connections.add(conn)
            return self._local.conn

    # --- low level -----------------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur

    def query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # --- jobs ----------------------------------------------------------------
    def create_job(self, job_id: str, prompt: str, template_id: Optional[str]) -> None:
        now = time.time()
        self.execute(
            "INSERT INTO jobs (id, prompt, status, template_id, created_at, updated_at) "
            "VALUES (?, ?, 'queued', ?, ?, ?)",
            (job_id, prompt, template_id, now, now),
        )

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.execute(
            f"UPDATE jobs SET {cols} WHERE id = ?",
            (*fields.values(), job_id),
        )

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))

    def next_queued_job(self) -> Optional[Dict[str, Any]]:
        return self.query_one(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        )

    def count_running(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM jobs WHERE status = 'running'")
        return int(row["c"]) if row else 0

    # --- events --------------------------------------------------------------
    def add_event(self, job_id: str, message: str, stage: str = "", level: str = "info") -> None:
        self.execute(
            "INSERT INTO job_events (job_id, stage, level, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_id, stage, level, message, time.time()),
        )

    def get_events(self, job_id: str) -> List[Dict[str, Any]]:
        return self.query(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY id ASC", (job_id,)
        )

    def get_job_timeline(self, job_id: str) -> List[str]:
        events = self.get_events(job_id)
        timeline = []
        for e in events:
            # Convert timestamp to HH:MM:SS
            import datetime
            dt = datetime.datetime.fromtimestamp(e["created_at"])
            ts = dt.strftime("%H:%M:%S")
            stage = f"[{e['stage']}]" if e['stage'] else "[system]"
            timeline.append(f"{ts} {stage} {e['message']}")
        return timeline

    # --- assets --------------------------------------------------------------
    def add_asset(self, asset: Dict[str, Any]) -> None:
        self.execute(
            "INSERT OR REPLACE INTO assets (id, job_id, role, name, source, source_url, "
            "file_path, file_hash, file_size, format, quality_score, metadata_json, "
            "dependencies_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                asset["id"], asset.get("job_id"), asset.get("role"), asset.get("name"),
                asset.get("source"), asset.get("source_url"), asset.get("file_path"),
                asset.get("file_hash"), asset.get("file_size"), asset.get("format"),
                asset.get("quality_score"),
                json.dumps(asset.get("metadata", {})),
                json.dumps(asset.get("dependencies", [])),
                time.time(),
            ),
        )

    def get_asset_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        return self.query_one("SELECT * FROM assets WHERE file_hash = ? LIMIT 1", (file_hash,))

    def get_assets_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        return self.query("SELECT * FROM assets WHERE job_id = ? ORDER BY created_at ASC", (job_id,))

    def list_assets(self, limit: int = 200, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all assets, optionally filtered by a substring search on name or source."""
        if search:
            pattern = f"%{search}%"
            return self.query(
                "SELECT * FROM assets WHERE name LIKE ? OR source LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (pattern, pattern, limit),
            )
        return self.query("SELECT * FROM assets ORDER BY created_at DESC LIMIT ?", (limit,))

    # --- memory --------------------------------------------------------------
    def add_memory(self, job_id: str, prompt: str, template_id: str, outcome: str,
                   summary: Dict[str, Any]) -> None:
        self.execute(
            "INSERT INTO memory (job_id, prompt, template_id, outcome, summary_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (job_id, prompt, template_id, outcome, json.dumps(summary), time.time()),
        )

    def recall_memory(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.query("SELECT * FROM memory ORDER BY created_at DESC LIMIT ?", (limit,))

    def find_similar_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        return self.query_one(
            "SELECT * FROM memory WHERE prompt = ? AND outcome = 'success' "
            "ORDER BY created_at DESC LIMIT 1",
            (prompt,),
        )

    # --- failure/strategy memory ---------------------------------------------
    def add_failure_memory(self, prompt: str, error: str, context: Dict[str, Any]) -> None:
        self.execute(
            "INSERT INTO failure_memory (prompt, error, context_json, created_at) VALUES (?,?,?,?)",
            (prompt, error, json.dumps(context), time.time())
        )

    def get_failure_memories(self, prompt: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM failure_memory WHERE prompt = ? ORDER BY created_at DESC LIMIT ?",
            (prompt, limit)
        )
        for r in rows:
            if r.get("context_json"):
                try:
                    r["context"] = json.loads(r["context_json"])
                except Exception:
                    r["context"] = {}
        return rows

    def add_strategy_memory(self, prompt: str, strategy: Dict[str, Any], outcome: str) -> None:
        self.execute(
            "INSERT INTO strategy_memory (prompt, strategy_json, outcome, created_at) VALUES (?,?,?,?)",
            (prompt, json.dumps(strategy), outcome, time.time())
        )

    def get_strategy_memories(self, prompt: str, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM strategy_memory WHERE prompt = ? ORDER BY created_at DESC LIMIT ?",
            (prompt, limit)
        )
        for r in rows:
            if r.get("strategy_json"):
                try:
                    r["strategy"] = json.loads(r["strategy_json"])
                except Exception:
                    r["strategy"] = {}
        return rows

    def add_world_model_entry(self, job_id: str, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO world_model (job_id, key, value_json, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(job_id, key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (job_id, key, json.dumps(value), time.time()),
        )

    def get_world_model_entries(self, job_id: str) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM world_model WHERE job_id = ? ORDER BY updated_at ASC",
            (job_id,),
        )
        for r in rows:
            if r.get("value_json"):
                try:
                    r["value"] = json.loads(r["value_json"])
                except Exception:
                    r["value"] = None
        return rows

    # --- project hierarchy & embeddings cache ---------------------------------
    def add_hierarchy_node(self, node_id: str, project_id: str, parent_id: Optional[str],
                           node_type: str, name: str, status: str = 'pending',
                           estimated_duration: float = 0.0, dependencies: List[str] = None,
                           metadata: Dict[str, Any] = None) -> None:
        now = time.time()
        self.execute(
            "INSERT OR REPLACE INTO project_hierarchy "
            "(id, project_id, parent_id, node_type, name, status, estimated_duration, "
            "actual_duration, dependencies_json, metadata_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,0.0,?,?,?,?)",
            (
                node_id, project_id, parent_id, node_type, name, status, estimated_duration,
                json.dumps(dependencies or []), json.dumps(metadata or {}), now, now
            )
        )

    def update_hierarchy_node_status(self, node_id: str, status: str,
                                     actual_duration: Optional[float] = None) -> None:
        now = time.time()
        if actual_duration is not None:
            self.execute(
                "UPDATE project_hierarchy SET status = ?, actual_duration = ?, updated_at = ? WHERE id = ?",
                (status, actual_duration, now, node_id)
            )
        else:
            self.execute(
                "UPDATE project_hierarchy SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, node_id)
            )

    def get_project_hierarchy(self, project_id: str) -> List[Dict[str, Any]]:
        rows = self.query("SELECT * FROM project_hierarchy WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
        for r in rows:
            if r.get("dependencies_json"):
                try:
                    r["dependencies"] = json.loads(r["dependencies_json"])
                except Exception:
                    r["dependencies"] = []
            else:
                r["dependencies"] = []
            if r.get("metadata_json"):
                try:
                    r["metadata"] = json.loads(r["metadata_json"])
                except Exception:
                    r["metadata"] = {}
            else:
                r["metadata"] = {}
        return rows

    def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        import hashlib
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        row = self.query_one("SELECT embedding_json FROM embeddings_cache WHERE text_hash = ?", (text_hash,))
        if row and row.get("embedding_json"):
            try:
                return json.loads(row["embedding_json"])
            except Exception:
                pass
        return None

    def cache_embedding(self, text: str, embedding: List[float]) -> None:
        import hashlib
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        now = time.time()
        self.execute(
            "INSERT OR REPLACE INTO embeddings_cache (text_hash, text_content, embedding_json, created_at) "
            "VALUES (?,?,?,?)",
            (text_hash, text, json.dumps(embedding), now)
        )

    def add_procedural_memory(self, task_type: str, recipe: Dict[str, Any], outcome: str) -> None:
        self.execute(
            "INSERT INTO procedural_memory (task_type, recipe_json, outcome, created_at) VALUES (?,?,?,?)",
            (task_type, json.dumps(recipe), outcome, time.time())
        )

    def get_procedural_memories(self, task_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM procedural_memory WHERE task_type = ? ORDER BY created_at DESC LIMIT ?",
            (task_type, limit)
        )
        for r in rows:
            if r.get("recipe_json"):
                try:
                    r["recipe"] = json.loads(r["recipe_json"])
                except Exception:
                    r["recipe"] = {}
        return rows

    # --- success memory ------------------------------------------------------
    def add_success_memory(self, job_id: str, prompt: str, template_id: str,
                           workers_used: List[str], assets_used: List[str],
                           completion_time_secs: float, generated_files: List[str],
                           reliability_score: float = 1.0) -> None:
        self.execute(
            "INSERT INTO success_memory (job_id, prompt, template_id, workers_used_json, "
            "assets_used_json, completion_time_secs, generated_files_json, reliability_score, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (job_id, prompt, template_id,
             json.dumps(workers_used), json.dumps(assets_used),
             completion_time_secs, json.dumps(generated_files),
             reliability_score, time.time())
        )

    def get_success_memories(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM success_memory ORDER BY reliability_score DESC, created_at DESC LIMIT ?",
            (limit,)
        )
        for r in rows:
            for field in ("workers_used_json", "assets_used_json", "generated_files_json"):
                key = field.replace("_json", "")
                if r.get(field):
                    try:
                        r[key] = json.loads(r[field])
                    except Exception:
                        r[key] = []
        return rows

    def find_similar_success(self, prompt: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns recent successes whose prompt shares keywords with the given prompt."""
        words = [w.strip().lower() for w in prompt.split() if len(w) > 3]
        if not words:
            return self.get_success_memories(limit)
        conditions = " OR ".join(["lower(prompt) LIKE ?" for _ in words])
        params = tuple(f"%{w}%" for w in words) + (limit,)
        rows = self.query(
            f"SELECT * FROM success_memory WHERE {conditions} "
            f"ORDER BY reliability_score DESC, created_at DESC LIMIT ?",
            params
        )
        for r in rows:
            for field in ("workers_used_json", "assets_used_json", "generated_files_json"):
                key = field.replace("_json", "")
                if r.get(field):
                    try:
                        r[key] = json.loads(r[field])
                    except Exception:
                        r[key] = []
        return rows

    # --- asset memory --------------------------------------------------------
    def record_asset_usage(self, asset_name: str, asset_source: str,
                           category: str, success: bool,
                           import_issue: Optional[str] = None) -> None:
        now = time.time()
        existing = self.query_one(
            "SELECT * FROM asset_memory WHERE asset_name=? AND asset_source=?",
            (asset_name, asset_source)
        )
        if existing:
            issues = []
            if existing.get("import_issues_json"):
                try:
                    issues = json.loads(existing["import_issues_json"])
                except Exception:
                    pass
            if import_issue:
                issues.append(import_issue)
            self.execute(
                "UPDATE asset_memory SET use_count=use_count+1, "
                "success_count=success_count+?, fail_count=fail_count+?, "
                "import_issues_json=?, last_used_at=? "
                "WHERE asset_name=? AND asset_source=?",
                (1 if success else 0, 0 if success else 1,
                 json.dumps(issues[-10:]), now, asset_name, asset_source)
            )
        else:
            issues = [import_issue] if import_issue else []
            self.execute(
                "INSERT INTO asset_memory (asset_name, asset_source, category, use_count, "
                "success_count, fail_count, import_issues_json, last_used_at) "
                "VALUES (?,?,?,1,?,?,?,?)",
                (asset_name, asset_source, category,
                 1 if success else 0, 0 if success else 1,
                 json.dumps(issues), now)
            )

    def get_best_assets_for_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Returns assets with highest success rate for a given category."""
        rows = self.query(
            "SELECT *, CAST(success_count AS REAL)/use_count AS success_rate "
            "FROM asset_memory WHERE category=? AND use_count>0 "
            "ORDER BY success_rate DESC, use_count DESC LIMIT ?",
            (category, limit)
        )
        for r in rows:
            if r.get("import_issues_json"):
                try:
                    r["import_issues"] = json.loads(r["import_issues_json"])
                except Exception:
                    r["import_issues"] = []
        return rows

    def get_all_asset_memory(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.query(
            "SELECT *, CAST(success_count AS REAL)/MAX(use_count,1) AS success_rate "
            "FROM asset_memory ORDER BY last_used_at DESC LIMIT ?",
            (limit,)
        )
        for r in rows:
            if r.get("import_issues_json"):
                try:
                    r["import_issues"] = json.loads(r["import_issues_json"])
                except Exception:
                    r["import_issues"] = []
        return rows

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                for conn in list(self._connections):
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._connections.clear()

