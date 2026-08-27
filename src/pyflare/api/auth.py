"""Authentication helpers and dependencies for PyFlare API."""
from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_bearer = HTTPBearer(auto_error=False)


def get_configured_api_key() -> Optional[str]:
    """Retrieve the configured API key from environment."""
    return os.environ.get("PYFLARE_API_KEY") or os.environ.get("APPSUITE_API_KEY")


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> bool:
    """
    Validate that incoming request has a valid API key when authentication is configured.
    Supports either 'X-API-Key: <key>' or 'Authorization: Bearer <key>' headers.
    """
    configured_key = get_configured_api_key()
    
    # If no key is set and authentication is not strictly forced, allow access
    require_auth = os.environ.get("PYFLARE_REQUIRE_AUTH", "false").lower() in ("1", "true", "yes")
    if not configured_key:
        if require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required but no PYFLARE_API_KEY configured",
            )
        return True

    provided_token: Optional[str] = None
    if x_api_key:
        provided_token = x_api_key
    elif auth_header and auth_header.credentials:
        provided_token = auth_header.credentials

    if not provided_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required API key (provide via 'X-API-Key' or 'Authorization: Bearer <token>')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(provided_token.encode("utf-8"), configured_key.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
