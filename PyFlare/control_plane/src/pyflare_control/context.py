"""Production-grade project context management for PyFlare Game Developer beta.

Implements project registration, structure awareness, deterministic indexing,
change detection, secret exclusion, project isolation, and bounded retrieval.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ProjectContextError(RuntimeError):
    """Base error for project context operations."""


class ProjectNotFoundError(ProjectContextError):
    """Raised when a requested project ID is not found."""


class StaleIndexError(ProjectContextError):
    """Raised when context retrieval is attempted on an un-indexed or stale project."""


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    project_id: str
    name: str
    root_path: str
    project_type: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class RetrievedSource:
    rel_path: str
    start_line: int
    end_line: int
    score: float
    reason: str
    content: str


@dataclass(frozen=True, slots=True)
class TaskContext:
    project_id: str
    query: str
    sources: tuple[RetrievedSource, ...]
    formatted_context: str
    estimated_tokens: int
    total_characters: int


@dataclass(frozen=True, slots=True)
class IndexReport:
    project_id: str
    indexed_files: int
    skipped_files: int
    removed_files: int
    total_chunks: int
    duration_seconds: float
    warnings: tuple[str, ...]


# ── Sensitive File & Path Exclusions ──────────────────────────────────────────

DEFAULT_EXCLUDED_PATTERNS: tuple[str, ...] = (
    # Secrets & Credentials
    ".env",
    ".env.*",
    "*.env",
    "*secret*",
    "*credentials*",
    "*token*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "id_rsa*",
    "id_ed25519*",
    "*.keystore",
    "*.jks",
    # Unity Engine Caches & Artifacts
    "Library",
    "Library/*",
    "Temp",
    "Temp/*",
    "Obj",
    "Obj/*",
    "Build",
    "Build/*",
    "Builds",
    "Builds/*",
    "Logs",
    "Logs/*",
    "MemoryCaptures",
    "MemoryCaptures/*",
    "UserSettings",
    "UserSettings/*",
    # Generic VCS & Dependencies
    ".git",
    ".git/*",
    ".svn",
    ".vs",
    ".idea",
    ".vscode",
    "__pycache__",
    "__pycache__/*",
    "node_modules",
    "node_modules/*",
    "dist",
    "target",
)

DEFAULT_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # C# & Unity Scripts / Assembly
        ".cs",
        ".asmdef",
        ".asmref",
        ".shader",
        ".compute",
        ".hlsl",
        ".cginc",
        ".uss",
        ".uxml",
        # Documents & Configurations
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".txt",
        ".md",
        ".ini",
        ".cfg",
        # Python & System Scripts
        ".py",
        ".sh",
        ".bat",
        ".ps1",
    }
)

MAX_INDEXABLE_FILE_SIZE_BYTES = 512 * 1024  # 512 KB


# ── Context Manager Implementation ───────────────────────────────────────────

class ProjectContextManager:
    """Deterministic, isolated, SQLite-backed project context manager."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._initialize_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    project_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS indexed_files (
                    project_id TEXT NOT NULL,
                    rel_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, rel_path),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS file_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    rel_path TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    tokens_estimate INTEGER NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_project
                    ON file_chunks(project_id);
                """
            )

    # ── Project Registration ──────────────────────────────────────────────────

    def register_project(
        self,
        project_id: str,
        root_path: Path,
        *,
        name: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
    ) -> ProjectInfo:
        root_path = root_path.resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"project root path does not exist or is not a directory: {root_path}")

        proj_name = name or root_path.name
        proj_type, detected_meta = self._detect_project_structure(root_path)
        combined_meta = {**detected_meta, **(custom_metadata or {})}

        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    project_id, name, root_path, project_type, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name = excluded.name,
                    root_path = excluded.root_path,
                    project_type = excluded.project_type,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    proj_name,
                    str(root_path),
                    proj_type,
                    json.dumps(combined_meta, sort_keys=True),
                    now,
                    now,
                ),
            )

        return ProjectInfo(
            project_id=project_id,
            name=proj_name,
            root_path=str(root_path),
            project_type=proj_type,
            metadata=combined_meta,
            created_at=now,
            updated_at=now,
        )

    def get_project(self, project_id: str) -> ProjectInfo:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row:
            raise ProjectNotFoundError(f"project not registered: {project_id}")

        return ProjectInfo(
            project_id=row["project_id"],
            name=row["name"],
            root_path=row["root_path"],
            project_type=row["project_type"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ── Project Structure Detection ───────────────────────────────────────────

    def _detect_project_structure(self, root_path: Path) -> tuple[str, dict[str, Any]]:
        assets_dir = root_path / "Assets"
        proj_settings = root_path / "ProjectSettings"

        if assets_dir.is_dir() and proj_settings.is_dir():
            unity_version = "unknown"
            version_file = proj_settings / "ProjectVersion.txt"
            if version_file.is_file():
                for line in version_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("m_EditorVersion:"):
                        unity_version = line.split(":", 1)[1].strip()
                        break

            scenes: list[str] = []
            asmdefs: list[str] = []
            for item in assets_dir.rglob("*"):
                if item.is_file():
                    if item.suffix == ".unity":
                        scenes.append(str(item.relative_to(root_path)).replace("\\", "/"))
                    elif item.suffix == ".asmdef":
                        asmdefs.append(str(item.relative_to(root_path)).replace("\\", "/"))

            return "unity", {
                "unity_version": unity_version,
                "scenes": sorted(scenes),
                "asmdefs": sorted(asmdefs),
                "has_packages": (root_path / "Packages").is_dir(),
            }

        return "generic", {"detected_at": datetime.now(UTC).isoformat()}

    # ── Secret and Hygiene Filtering ──────────────────────────────────────────

    @staticmethod
    def is_excluded_path(rel_path_str: str) -> bool:
        normalized = rel_path_str.replace("\\", "/")
        parts = normalized.split("/")

        # Check part-based exclusions
        for part in parts:
            for pattern in DEFAULT_EXCLUDED_PATTERNS:
                if "/" not in pattern and fnmatch.fnmatch(part.lower(), pattern.lower()):
                    return True

        # Check whole-path exclusions
        for pattern in DEFAULT_EXCLUDED_PATTERNS:
            if "/" in pattern:
                clean_pattern = pattern.rstrip("/*")
                if normalized == clean_pattern or normalized.startswith(clean_pattern + "/"):
                    return True
                if fnmatch.fnmatch(normalized.lower(), pattern.lower()):
                    return True

        return False

    # ── Indexing and Refreshing ───────────────────────────────────────────────

    def index_project(self, project_id: str, *, force_full: bool = False) -> IndexReport:
        project = self.get_project(project_id)
        root = Path(project.root_path)
        start_time = datetime.now(UTC)
        warnings: list[str] = []

        if not root.exists():
            raise ProjectContextError(f"project root directory missing: {root}")

        with self._connect() as conn:
            existing_files = {
                row["rel_path"]: (row["sha256"], row["mtime"])
                for row in conn.execute(
                    "SELECT rel_path, sha256, mtime FROM indexed_files WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            }

        found_rel_paths: set[str] = set()
        indexed_count = 0
        skipped_count = 0
        removed_count = 0

        # Scan files
        for root_dir, dir_names, file_names in os.walk(root):
            # Prune excluded directories in-place for efficiency
            rel_dir = os.path.relpath(root_dir, root)
            if rel_dir == ".":
                rel_dir = ""
            dir_names[:] = [
                d
                for d in dir_names
                if not self.is_excluded_path(
                    (rel_dir + "/" + d if rel_dir else d).replace("\\", "/")
                )
            ]

            for file_name in file_names:
                rel_file = (rel_dir + "/" + file_name if rel_dir else file_name).replace("\\", "/")
                if self.is_excluded_path(rel_file):
                    skipped_count += 1
                    continue

                file_path = Path(root_dir) / file_name
                suffix = file_path.suffix.lower()
                if suffix not in DEFAULT_SUPPORTED_EXTENSIONS:
                    skipped_count += 1
                    continue

                found_rel_paths.add(rel_file)

                try:
                    stat = file_path.stat()
                except OSError as exc:
                    warnings.append(f"failed to stat {rel_file}: {exc}")
                    continue

                if stat.st_size > MAX_INDEXABLE_FILE_SIZE_BYTES:
                    warnings.append(
                        f"skipped {rel_file}: file size {stat.st_size} exceeds {MAX_INDEXABLE_FILE_SIZE_BYTES} bytes"
                    )
                    skipped_count += 1
                    continue

                try:
                    file_bytes = file_path.read_bytes()
                except OSError as exc:
                    warnings.append(f"failed to read {rel_file}: {exc}")
                    continue

                sha256 = hashlib.sha256(file_bytes).hexdigest()

                if not force_full and rel_file in existing_files:
                    prev_sha256, prev_mtime = existing_files[rel_file]
                    if prev_sha256 == sha256 and abs(prev_mtime - stat.st_mtime) < 1e-4:
                        continue

                try:
                    text_content = file_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        text_content = file_bytes.decode("latin-1")
                    except Exception:
                        warnings.append(f"skipped non-decodable text file: {rel_file}")
                        skipped_count += 1
                        continue

                chunks = self._chunk_file(text_content, rel_file)
                self._persist_file_index(project_id, rel_file, sha256, stat.st_size, stat.st_mtime, chunks)
                indexed_count += 1

        # Clean up files that were deleted on disk
        deleted_files = set(existing_files.keys()) - found_rel_paths
        if deleted_files:
            with self._connect() as conn:
                for del_path in deleted_files:
                    conn.execute(
                        "DELETE FROM file_chunks WHERE project_id = ? AND rel_path = ?",
                        (project_id, del_path),
                    )
                    conn.execute(
                        "DELETE FROM indexed_files WHERE project_id = ? AND rel_path = ?",
                        (project_id, del_path),
                    )
            removed_count = len(deleted_files)

        with self._connect() as conn:
            total_chunks = conn.execute(
                "SELECT COUNT(*) FROM file_chunks WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]

        duration = (datetime.now(UTC) - start_time).total_seconds()
        return IndexReport(
            project_id=project_id,
            indexed_files=indexed_count,
            skipped_files=skipped_count,
            removed_files=removed_count,
            total_chunks=total_chunks,
            duration_seconds=duration,
            warnings=tuple(warnings),
        )

    def is_stale(self, project_id: str) -> bool:
        project = self.get_project(project_id)
        root = Path(project.root_path)
        if not root.exists():
            return True

        with self._connect() as conn:
            existing = {
                row["rel_path"]: (row["sha256"], row["size_bytes"], row["mtime"])
                for row in conn.execute(
                    "SELECT rel_path, sha256, size_bytes, mtime FROM indexed_files WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            }

        if not existing:
            return True

        found_count = 0
        for root_dir, dir_names, file_names in os.walk(root):
            rel_dir = os.path.relpath(root_dir, root)
            if rel_dir == ".":
                rel_dir = ""
            dir_names[:] = [
                d
                for d in dir_names
                if not self.is_excluded_path(
                    (rel_dir + "/" + d if rel_dir else d).replace("\\", "/")
                )
            ]

            for file_name in file_names:
                rel_file = (rel_dir + "/" + file_name if rel_dir else file_name).replace("\\", "/")
                if self.is_excluded_path(rel_file):
                    continue
                file_path = Path(root_dir) / file_name
                if file_path.suffix.lower() not in DEFAULT_SUPPORTED_EXTENSIONS:
                    continue

                found_count += 1
                if rel_file not in existing:
                    return True

                try:
                    stat = file_path.stat()
                except OSError:
                    return True

                prev_sha, prev_size, prev_mtime = existing[rel_file]
                if stat.st_size != prev_size:
                    return True
                if abs(stat.st_mtime - prev_mtime) >= 1e-4:
                    try:
                        cur_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
                        if cur_sha != prev_sha:
                            return True
                    except OSError:
                        return True

        return found_count != len(existing)

    def _chunk_file(
        self,
        text: str,
        rel_path: str,
        chunk_lines: int = 40,
        overlap_lines: int = 8,
    ) -> list[tuple[int, int, str, int]]:
        lines = text.splitlines(keepends=True)
        if not lines:
            return [(1, 1, "", 0)]

        total_lines = len(lines)
        step = max(1, chunk_lines - overlap_lines)
        chunks: list[tuple[int, int, str, int]] = []

        start = 0
        while start < total_lines:
            end = min(total_lines, start + chunk_lines)
            chunk_content = "".join(lines[start:end])
            tokens_estimate = max(1, len(chunk_content) // 4)
            chunks.append((start + 1, end, chunk_content, tokens_estimate))
            if end >= total_lines:
                break
            start += step

        return chunks

    def _persist_file_index(
        self,
        project_id: str,
        rel_path: str,
        sha256: str,
        size_bytes: int,
        mtime: float,
        chunks: list[tuple[int, int, str, int]],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM file_chunks WHERE project_id = ? AND rel_path = ?",
                (project_id, rel_path),
            )
            conn.execute(
                """
                INSERT INTO indexed_files (
                    project_id, rel_path, sha256, size_bytes, mtime, chunk_count, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, rel_path) DO UPDATE SET
                    sha256 = excluded.sha256,
                    size_bytes = excluded.size_bytes,
                    mtime = excluded.mtime,
                    chunk_count = excluded.chunk_count,
                    indexed_at = excluded.indexed_at
                """,
                (project_id, rel_path, sha256, size_bytes, mtime, len(chunks), now),
            )

            chunk_rows = [
                (uuid.uuid4().hex, project_id, rel_path, start_line, end_line, content, tokens)
                for start_line, end_line, content, tokens in chunks
            ]
            conn.executemany(
                """
                INSERT INTO file_chunks (
                    chunk_id, project_id, rel_path, start_line, end_line, content, tokens_estimate
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                chunk_rows,
            )

    # ── Context Retrieval & Assembly ──────────────────────────────────────────

    def retrieve_context(
        self,
        project_id: str,
        query: str,
        *,
        max_tokens: int = 4000,
        max_snippets: int = 10,
    ) -> TaskContext:
        """Deterministically retrieves relevant project context bounded by max_tokens."""
        # Project isolation guarantee: verify project exists
        project = self.get_project(project_id)

        # Check if indexed
        with self._connect() as conn:
            chunk_rows = conn.execute(
                """
                SELECT chunk_id, rel_path, start_line, end_line, content, tokens_estimate
                FROM file_chunks
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchall()

        if not chunk_rows:
            return TaskContext(
                project_id=project_id,
                query=query,
                sources=(),
                formatted_context="",
                estimated_tokens=0,
                total_characters=0,
            )

        query_terms = self._tokenize(query)
        scored_candidates: list[tuple[float, str, dict[str, Any]]] = []

        for row in chunk_rows:
            rel_path = row["rel_path"]
            content = row["content"]
            score, reason = self._score_chunk(query_terms, query, rel_path, content)
            if score > 0.0:
                scored_candidates.append(
                    (
                        score,
                        reason,
                        {
                            "rel_path": rel_path,
                            "start_line": row["start_line"],
                            "end_line": row["end_line"],
                            "content": content,
                            "tokens": row["tokens_estimate"],
                        },
                    )
                )

        # Sort deterministically: highest score first, tie-break by rel_path and line
        scored_candidates.sort(
            key=lambda item: (
                -item[0],
                item[2]["rel_path"],
                item[2]["start_line"],
            )
        )

        selected_sources: list[RetrievedSource] = []
        accumulated_tokens = 0
        total_chars = 0
        context_blocks: list[str] = [
            f"# PyFlare Project Context: {project.name} ({project.project_type})\n"
        ]

        for score, reason, data in scored_candidates:
            if len(selected_sources) >= max_snippets:
                break

            tokens = data["tokens"]
            if accumulated_tokens + tokens > max_tokens and selected_sources:
                continue  # Skip if exceeding token budget

            source = RetrievedSource(
                rel_path=data["rel_path"],
                start_line=data["start_line"],
                end_line=data["end_line"],
                score=round(score, 4),
                reason=reason,
                content=data["content"],
            )
            selected_sources.append(source)
            accumulated_tokens += tokens
            total_chars += len(data["content"])

            ext = Path(data["rel_path"]).suffix.lstrip(".") or "txt"
            context_blocks.append(
                f"### File: {data['rel_path']} (Lines {data['start_line']}-{data['end_line']})\n"
                f"*Retrieval Reason: {reason} (Score: {round(score, 2)})*\n"
                f"```{ext}\n"
                f"{data['content'].rstrip()}\n"
                f"```\n"
            )

        formatted_context = "\n".join(context_blocks)
        return TaskContext(
            project_id=project_id,
            query=query,
            sources=tuple(selected_sources),
            formatted_context=formatted_context,
            estimated_tokens=accumulated_tokens,
            total_characters=total_chars,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        # Split on non-alphanumeric, preserve camelCase boundaries
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+|[a-zA-Z]+", text)
        return [p.lower() for p in parts if len(p) > 1]

    def _score_chunk(
        self,
        query_terms: list[str],
        raw_query: str,
        rel_path: str,
        content: str,
    ) -> tuple[float, str]:
        if not query_terms:
            return 0.0, "empty query"

        content_lower = content.lower()
        path_lower = rel_path.lower()
        reasons: list[str] = []
        score = 0.0

        # 1. Exact raw phrase match
        if len(raw_query) > 3 and raw_query.lower() in content_lower:
            score += 50.0
            reasons.append("exact query phrase match in content")

        # 2. File path relevance
        matched_path_terms = [t for t in query_terms if t in path_lower]
        if matched_path_terms:
            path_bonus = len(matched_path_terms) * 15.0
            score += path_bonus
            reasons.append(f"matched path terms {matched_path_terms}")

        # 3. Content term frequencies
        matched_content_terms: list[str] = []
        term_freqs = Counter(self._tokenize(content))
        for term in query_terms:
            count = term_freqs.get(term, 0)
            if count > 0:
                matched_content_terms.append(term)
                # Sub-linear term frequency scoring
                score += (1.0 + math.log(count)) * 5.0

        if matched_content_terms:
            reasons.append(f"matched terms {matched_content_terms} in body")

        return score, "; ".join(reasons) if reasons else "no match"
