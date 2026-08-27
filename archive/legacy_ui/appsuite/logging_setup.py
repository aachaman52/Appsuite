"""Centralised logging configuration."""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
import threading
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


class SQLiteLogHandler(logging.Handler):
    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = str(db_path)
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Initialize schema
        with sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS structured_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    level VARCHAR(20),
                    worker VARCHAR(100),
                    job_id VARCHAR(100),
                    execution_id VARCHAR(100),
                    message TEXT,
                    runtime REAL,
                    memory_usage REAL,
                    cpu_usage REAL,
                    gpu_usage REAL
                )
            ''')
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        with self._lock:
            if not hasattr(self._local, "conn"):
                conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL;")
                self._local.conn = conn
            return self._local.conn

    def emit(self, record: logging.LogRecord):
        try:
            conn = self._get_conn()
            msg = self.format(record)
            
            # Extract structured fields if they exist in record.__dict__
            worker = getattr(record, 'worker', record.name)
            job_id = getattr(record, 'job_id', '')
            execution_id = getattr(record, 'execution_id', '')
            runtime = getattr(record, 'runtime', 0.0)
            memory_usage = getattr(record, 'memory_usage', 0.0)
            cpu_usage = getattr(record, 'cpu_usage', 0.0)
            gpu_usage = getattr(record, 'gpu_usage', 0.0)

            conn.execute(
                "INSERT INTO structured_logs (timestamp, level, worker, job_id, execution_id, message, runtime, memory_usage, cpu_usage, gpu_usage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record.created, record.levelname, worker, job_id, execution_id, msg, runtime, memory_usage, cpu_usage, gpu_usage)
            )
            conn.commit()
        except Exception:
            self.handleError(record)

class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "worker": getattr(record, 'worker', record.name),
            "job_id": getattr(record, 'job_id', ''),
            "execution_id": getattr(record, 'execution_id', ''),
            "message": record.getMessage(),
            "runtime": getattr(record, 'runtime', 0.0),
            "memory_usage": getattr(record, 'memory_usage', 0.0),
            "cpu_usage": getattr(record, 'cpu_usage', 0.0),
            "gpu_usage": getattr(record, 'gpu_usage', 0.0)
        }
        return json.dumps(log_data)

class NoisyLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out noisy token streaming from the console, assuming it's from 'provider_manager'
        if record.name == "provider_manager" and record.levelno < logging.WARNING:
            return False
        return True

def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 1. Console Handler (Human readable)
    console_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(console_fmt)
    console.addFilter(NoisyLogFilter())
    root.addHandler(console)

    # 2. File Handler (JSON Structured)
    json_fmt = StructuredJsonFormatter()
    file_handler = RotatingFileHandler(
        log_dir / "appsuite.json.log", maxBytes=10_000_000, backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(json_fmt)
    root.addHandler(file_handler)
    
    # 3. SQLite Handler
    sqlite_handler = SQLiteLogHandler(log_dir / "logs.db")
    sqlite_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(sqlite_handler)

    _configured = True

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

class StructuredLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs

def get_structured_logger(name: str, job_id: str = "", execution_id: str = "") -> logging.LoggerAdapter:
    logger = get_logger(name)
    if not execution_id:
        execution_id = str(uuid.uuid4())
    return StructuredLoggerAdapter(logger, {"worker": name, "job_id": job_id, "execution_id": execution_id})