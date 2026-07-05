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

CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(file_hash);
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

