"""Unit tests for PyFlare security primitives."""
import os
import pytest
from pathlib import Path

from pyflare.core.security import (
    DEFAULT_ALLOWLIST,
    redact_secrets,
    resolve_workspace_path,
    run_safe_command,
)


@pytest.mark.unit
def test_secret_redaction():
    """Verify secrets are scrubbed from log strings and error messages."""
    text_with_key = "Failed request with api_key='sk-1234567890abcdef1234567890'"
    redacted = redact_secrets(text_with_key)
    assert "sk-1234567890abcdef1234567890" not in redacted
    assert "[REDACTED]" in redacted

    text_with_bearer = "Authorization: Bearer mySecretToken12345678"
    redacted_bearer = redact_secrets(text_with_bearer)
    assert "mySecretToken12345678" not in redacted_bearer
    assert "[REDACTED]" in redacted_bearer


@pytest.mark.unit
def test_workspace_path_resolution_safe(tmp_path: Path):
    """Verify safe paths within workspace resolve properly."""
    workspace = tmp_path / "test_ws"
    workspace.mkdir(parents=True, exist_ok=True)

    safe_target = "scenes/main.tscn"
    resolved = resolve_workspace_path(safe_target, workspace_root=workspace)
    assert resolved == (workspace / "scenes" / "main.tscn").resolve()
    assert str(resolved).startswith(str(workspace.resolve()))


@pytest.mark.unit
def test_workspace_path_traversal_blocked(tmp_path: Path):
    """Verify directory traversal attempts are blocked with PermissionError."""
    workspace = tmp_path / "test_ws"
    workspace.mkdir(parents=True, exist_ok=True)

    # Relative traversal attack
    with pytest.raises(PermissionError, match="Path traversal access denied"):
        resolve_workspace_path("../../etc/passwd", workspace_root=workspace)

    with pytest.raises(PermissionError, match="Path traversal access denied"):
        resolve_workspace_path("../outside.txt", workspace_root=workspace)

    # Absolute path escaping workspace
    system_path = tmp_path / "secret_system_dir"
    system_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PermissionError, match="Path traversal access denied"):
        resolve_workspace_path(system_path / "secret.key", workspace_root=workspace)


@pytest.mark.unit
def test_workspace_path_null_byte_blocked(tmp_path: Path):
    """Verify null bytes are rejected with ValueError."""
    workspace = tmp_path / "test_ws"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="null byte"):
        resolve_workspace_path("valid_file.txt\x00.exe", workspace_root=workspace)


@pytest.mark.unit
def test_safe_command_runner_allowlist():
    """Verify disallowed commands are blocked."""
    with pytest.raises(PermissionError, match="not in allowlist"):
        run_safe_command(["malicious_shell_script.sh"])

    with pytest.raises(PermissionError, match="not in allowlist"):
        run_safe_command(["bash", "-c", "rm -rf /"])


@pytest.mark.unit
def test_safe_command_runner_execution(tmp_path: Path):
    """Verify allowed commands run safely without shell=True."""
    proc = run_safe_command(["python", "-c", "print('safe execution')"], cwd=tmp_path)
    assert proc.returncode == 0
    assert "safe execution" in proc.stdout
