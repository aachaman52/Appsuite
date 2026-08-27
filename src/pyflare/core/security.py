"""
Security primitives for PyFlare:
- Workspace path traversal validation
- Allowlisted safe subprocess runner
- Secret and sensitive data redaction
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Set, Union


DEFAULT_ALLOWLIST: Set[str] = {
    "python",
    "python3",
    "py",
    "pytest",
    "git",
    "blender",
    "godot",
    "ffmpeg",
    "ffprobe",
    "mypy",
    "ruff",
}

SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|password|token|bearer|authorization)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),
    re.compile(r"(ghp_[a-zA-Z0-9]{20,})"),
    re.compile(r"(Bearer\s+[a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive API keys, passwords, and tokens from strings."""
    if not isinstance(text, str) or not text:
        return text
    
    redacted = text
    for pattern in SECRET_PATTERNS:
        # If pattern has groups, redact the sensitive group
        if pattern.groups == 2:
            redacted = pattern.sub(r"\1=[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
            
    # Also redact known environment variable secret values if set
    for env_var in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NVIDIA_API_KEY", "PYFLARE_API_KEY"):
        val = os.environ.get(env_var)
        if val and len(val) > 4 and val in redacted:
            redacted = redacted.replace(val, "[REDACTED]")
            
    return redacted


def get_default_workspace_dir() -> Path:
    """Get the configured or default workspace directory."""
    custom_ws = os.environ.get("PYFLARE_WORKSPACE_DIR")
    if custom_ws:
        p = Path(custom_ws).resolve()
    else:
        p = (Path.cwd() / "workspace").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_workspace_path(
    user_path: Union[str, Path],
    workspace_root: Optional[Union[str, Path]] = None,
    allow_creation: bool = True,
) -> Path:
    """
    Resolve and validate a path to ensure it is contained within the workspace root.
    Prevents path traversal vulnerabilities (e.g. '../', absolute system paths).

    Raises:
        PermissionError: if path escapes workspace root.
        ValueError: if user_path contains suspicious null bytes or control characters.
    """
    if "\x00" in str(user_path):
        raise ValueError("Invalid path: null byte detected")

    if workspace_root is None:
        root = get_default_workspace_dir()
    else:
        root = Path(workspace_root).resolve()
        if allow_creation:
            root.mkdir(parents=True, exist_ok=True)

    input_p = Path(user_path)
    if input_p.is_absolute():
        resolved = input_p.resolve()
    else:
        resolved = (root / input_p).resolve()

    try:
        # In Python 3.9+, is_relative_to is standard
        is_safe = resolved.is_relative_to(root)
    except AttributeError:
        try:
            resolved.relative_to(root)
            is_safe = True
        except ValueError:
            is_safe = False

    if not is_safe:
        raise PermissionError(
            f"Path traversal access denied: '{user_path}' resolves to '{resolved}' which is outside workspace '{root}'"
        )

    return resolved


def run_safe_command(
    cmd: Union[str, Sequence[str]],
    cwd: Optional[Union[str, Path]] = None,
    timeout: int = 120,
    allowlist: Optional[Set[str]] = None,
    env: Optional[dict] = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """
    Execute a subprocess safely without shell injection risks.
    - Uses shell=False
    - Checks the binary executable against an allowlist
    - Enforces execution timeout and terminates rogue child processes
    """
    if isinstance(cmd, str):
        cmd_args = shlex.split(cmd, posix=(os.name != "nt"))
    else:
        cmd_args = list(cmd)

    if not cmd_args:
        raise ValueError("Command list cannot be empty")

    binary = Path(cmd_args[0]).stem.lower()
    allowed = allowlist if allowlist is not None else DEFAULT_ALLOWLIST

    if binary not in allowed:
        raise PermissionError(
            f"Command execution blocked: '{binary}' is not in allowlist ({sorted(allowed)})"
        )

    exec_cwd = str(cwd) if cwd is not None else None
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        proc = subprocess.run(
            cmd_args,
            cwd=exec_cwd,
            timeout=timeout,
            shell=False,
            capture_output=capture_output,
            text=True,
            env=merged_env,
        )
        return proc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Command '{cmd_args[0]}' timed out after {timeout} seconds") from exc
