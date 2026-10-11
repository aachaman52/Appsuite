"""Authentication, session management, and credential security for PyFlare.

Implements local user identity, offline session lifecycle, secure credential storage,
separation of identity vs provider keys, expired session handling, and secret redaction.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class AuthError(RuntimeError):
    """Base exception for authentication and credential errors."""


class InvalidSessionError(AuthError):
    """Raised when a session token is invalid or does not exist."""


class SessionExpiredError(AuthError):
    """Raised when a valid session token has expired."""


class UserNotFoundError(AuthError):
    """Raised when user account is not found."""


class CredentialNotFoundError(AuthError):
    """Raised when requested provider credential does not exist."""


# ── Secret Sanitizer ──────────────────────────────────────────────────────────

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"nvapi-[a-zA-Z0-9_-]{32,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{16,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*[\"']([a-zA-Z0-9_\-]{8,})[\"']", re.IGNORECASE),
)


def sanitize_text(text: str) -> str:
    """Sanitize API keys, tokens, and credentials from text strings before logging or display."""
    if not text:
        return text

    sanitized = text
    # 1. Exact match replacements for known key formats
    for pattern in SECRET_PATTERNS[:3]:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)

    # 2. Bearer tokens
    sanitized = SECRET_PATTERNS[3].sub("Bearer [REDACTED_TOKEN]", sanitized)

    # 3. Key-value secrets
    def _kv_repl(m: re.Match[str]) -> str:
        key_name = m.group(1)
        return f'{key_name}="[REDACTED]"'

    sanitized = SECRET_PATTERNS[4].sub(_kv_repl, sanitized)
    return sanitized


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class UserIdentity:
    user_id: str
    username: str
    email: str
    display_name: str
    is_local: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    user_id: str
    token: str
    created_at: str
    expires_at: str
    is_revoked: bool

    @property
    def is_expired(self) -> bool:
        if self.is_revoked:
            return True
        exp = datetime.fromisoformat(self.expires_at)
        return datetime.now(UTC) >= exp


# ── Auth Manager & Credential Store ───────────────────────────────────────────

class AuthManager:
    """Manages local identities, sessions, and secure credentials in SQLite."""

    def __init__(self, db_path: Path, *, session_lifetime_hours: int = 24) -> None:
        self.db_path = db_path
        self.session_lifetime = timedelta(hours=session_lifetime_hours)
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
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_local INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    is_revoked INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS credentials (
                    provider_id TEXT PRIMARY KEY,
                    api_key TEXT NOT NULL,
                    base_url TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
            # Enforce 0600 file permissions on POSIX systems where chmod is supported
            try:
                os.chmod(self.db_path, 0o600)
            except (OSError, NotImplementedError):
                pass

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return salt.hex() + ":" + h.hex()

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        try:
            salt_hex, h_hex = hashed.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(h_hex)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    # ── User Identity ─────────────────────────────────────────────────────────

    def register_user(
        self,
        username: str,
        password: str,
        *,
        email: str = "",
        display_name: str | None = None,
        is_local: bool = True,
    ) -> UserIdentity:
        if not username:
            raise ValueError("username cannot be empty")
        if len(password) < 6:
            raise ValueError("password must be at least 6 characters")

        user_id = f"user_{secrets.token_hex(8)}"
        disp_name = display_name or username
        pw_hash = self._hash_password(password)
        now = datetime.now(UTC).isoformat()

        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, email, display_name, password_hash, is_local, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, username.lower().strip(), email, disp_name, pw_hash, 1 if is_local else 0, now),
                )
        except sqlite3.IntegrityError as exc:
            raise AuthError(f"username '{username}' already exists") from exc

        return UserIdentity(
            user_id=user_id,
            username=username.lower().strip(),
            email=email,
            display_name=disp_name,
            is_local=is_local,
            created_at=now,
        )

    def get_user(self, user_id: str) -> UserIdentity:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            raise UserNotFoundError(f"user not found: {user_id}")

        return UserIdentity(
            user_id=row["user_id"],
            username=row["username"],
            email=row["email"],
            display_name=row["display_name"],
            is_local=bool(row["is_local"]),
            created_at=row["created_at"],
        )

    # ── Session Handling ──────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> Session:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.lower().strip(),)
            ).fetchone()

        if not row or not self._verify_password(password, row["password_hash"]):
            raise AuthError("Invalid username or password")

        session_id = f"sess_{secrets.token_hex(12)}"
        token = secrets.token_hex(32)  # 64-character cryptographically secure token
        now_dt = datetime.now(UTC)
        expires_dt = now_dt + self.session_lifetime
        now_str = now_dt.isoformat()
        expires_str = expires_dt.isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, token, created_at, expires_at, is_revoked)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (session_id, row["user_id"], token, now_str, expires_str),
            )

        return Session(
            session_id=session_id,
            user_id=row["user_id"],
            token=token,
            created_at=now_str,
            expires_at=expires_str,
            is_revoked=False,
        )

    def validate_session(self, token: str) -> UserIdentity:
        if not token:
            raise InvalidSessionError("Token cannot be empty")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token = ?", (token,)
            ).fetchone()

        if not row:
            raise InvalidSessionError("Session does not exist")

        session = Session(
            session_id=row["session_id"],
            user_id=row["user_id"],
            token=row["token"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            is_revoked=bool(row["is_revoked"]),
        )

        if session.is_revoked:
            raise InvalidSessionError("Session has been revoked")

        if session.is_expired:
            raise SessionExpiredError("Session has expired; please log in again")

        return self.get_user(session.user_id)

    def logout(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET is_revoked = 1 WHERE token = ?", (token,)
            )

    # ── Credential Storage ────────────────────────────────────────────────────

    def set_provider_credential(
        self,
        provider_id: str,
        api_key: str,
        *,
        base_url: str | None = None,
    ) -> None:
        if not provider_id or not api_key:
            raise ValueError("provider_id and api_key are required")

        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO credentials (provider_id, api_key, base_url, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    api_key = excluded.api_key,
                    base_url = excluded.base_url,
                    updated_at = excluded.updated_at
                """,
                (provider_id.lower().strip(), api_key.strip(), base_url, now),
            )

    def get_provider_credential(self, provider_id: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT api_key FROM credentials WHERE provider_id = ?",
                (provider_id.lower().strip(),),
            ).fetchone()

        if not row:
            raise CredentialNotFoundError(f"no credential configured for provider '{provider_id}'")

        return row["api_key"]

    def list_configured_providers(self) -> tuple[str, ...]:
        """List provider IDs that have credentials configured, never exposing plaintext keys."""
        with self._connect() as conn:
            rows = conn.execute("SELECT provider_id FROM credentials ORDER BY provider_id").fetchall()
        return tuple(r["provider_id"] for r in rows)

    def delete_provider_credential(self, provider_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM credentials WHERE provider_id = ?",
                (provider_id.lower().strip(),),
            )
