"""Unit tests for PyFlare API authentication and access control."""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from pyflare.api.auth import verify_api_key


@pytest.mark.unit
def test_auth_enabled_by_default(monkeypatch):
    """By default, authentication is strictly enabled and unauthenticated access is rejected."""
    monkeypatch.delenv("PYFLARE_API_KEY", raising=False)
    monkeypatch.delenv("APPSUITE_API_KEY", raising=False)
    monkeypatch.delenv("PYFLARE_REQUIRE_AUTH", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(x_api_key=None, auth_header=None)
    assert exc_info.value.status_code == 401


@pytest.mark.unit
def test_auth_disabled_explicitly_allows_request(monkeypatch):
    """When require_auth=false is explicitly configured, requests pass."""
    monkeypatch.delenv("PYFLARE_API_KEY", raising=False)
    monkeypatch.delenv("APPSUITE_API_KEY", raising=False)
    monkeypatch.setenv("PYFLARE_REQUIRE_AUTH", "false")

    assert verify_api_key(x_api_key=None, auth_header=None) is True


@pytest.mark.unit
def test_auth_required_without_key_configured(monkeypatch):
    """When require_auth=true but no key is configured, raises 401."""
    monkeypatch.delenv("PYFLARE_API_KEY", raising=False)
    monkeypatch.delenv("APPSUITE_API_KEY", raising=False)
    monkeypatch.setenv("PYFLARE_REQUIRE_AUTH", "true")

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(x_api_key=None, auth_header=None)
    assert exc_info.value.status_code == 401


@pytest.mark.unit
def test_auth_with_valid_x_api_key(monkeypatch):
    """Providing correct X-API-Key passes."""
    monkeypatch.setenv("PYFLARE_API_KEY", "secret-test-key-12345")

    assert verify_api_key(x_api_key="secret-test-key-12345", auth_header=None) is True


@pytest.mark.unit
def test_auth_with_valid_bearer_token(monkeypatch):
    """Providing correct Authorization: Bearer <key> passes."""
    monkeypatch.setenv("PYFLARE_API_KEY", "secret-bearer-key-12345")

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-bearer-key-12345")
    assert verify_api_key(x_api_key=None, auth_header=credentials) is True


@pytest.mark.unit
def test_auth_with_invalid_key_rejected(monkeypatch):
    """Providing incorrect key raises 401."""
    monkeypatch.setenv("PYFLARE_API_KEY", "secret-test-key-12345")

    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(x_api_key="wrong-key", auth_header=None)
    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail
