"""Hardened Aachman Supabase Auth & Action Client for PyFlare.

Features:
- Stores sensitive tokens (access & refresh tokens) in OS Credential Manager (via keyring).
- Stores non-sensitive metadata (user ID, email, expires_at) in ~/.aachman/pyflare_session.json.
- Never stores passwords.
- Auto-refreshes access tokens and rotates refresh tokens.
- Never uses service_role or database passwords in client code.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
import requests

try:
    import keyring
except ImportError:
    keyring = None

from .constants import DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_ANON_KEY
from ..logging_setup import get_logger

log = get_logger("ecosystem.client")

KEYRING_SERVICE_NAME = "aachman_pyflare_auth"
KEYRING_USER_ACCESS_TOKEN = "access_token"
KEYRING_USER_REFRESH_TOKEN = "refresh_token"


class AachmanEcosystemClient:
    """Hardened Supabase client for PyFlare using OS Credential Storage."""

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        session_file: Optional[Path] = None,
    ):
        self.supabase_url = (supabase_url or os.environ.get("SUPABASE_URL") or DEFAULT_SUPABASE_URL).rstrip("/")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_ANON_KEY") or DEFAULT_SUPABASE_ANON_KEY

        if session_file is None:
            config_dir = Path.home() / ".aachman"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.session_file = config_dir / "pyflare_session.json"
        else:
            self.session_file = session_file

        self.metadata: Dict[str, Any] = {}
        self._in_memory_access_token: Optional[str] = None
        self._in_memory_refresh_token: Optional[str] = None

        self._load_metadata()
        self._load_credentials_from_keyring()

    def _load_metadata(self) -> None:
        """Load non-sensitive metadata from JSON file."""
        if self.session_file.exists():
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                log.warning(f"Could not load metadata from {self.session_file}: {e}")
                self.metadata = {}

    def _save_metadata(self) -> None:
        """Save non-sensitive metadata to JSON file (NO tokens/passwords)."""
        try:
            clean_meta = {
                "user_id": self.metadata.get("user_id"),
                "email": self.metadata.get("email"),
                "expires_at": self.metadata.get("expires_at"),
                "updated_at": int(time.time()),
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(clean_meta, f, indent=2)
        except Exception as e:
            log.warning(f"Could not save session metadata to {self.session_file}: {e}")

    def _load_credentials_from_keyring(self) -> None:
        """Retrieve access and refresh tokens from OS Credential Manager."""
        if keyring is not None:
            try:
                self._in_memory_access_token = keyring.get_password(
                    KEYRING_SERVICE_NAME, KEYRING_USER_ACCESS_TOKEN
                )
                self._in_memory_refresh_token = keyring.get_password(
                    KEYRING_SERVICE_NAME, KEYRING_USER_REFRESH_TOKEN
                )
            except Exception as e:
                log.warning(f"Failed reading tokens from OS Credential Store: {e}")

    def _save_credentials_to_keyring(self, access_token: str, refresh_token: str) -> None:
        """Store access and refresh tokens securely in OS Credential Store."""
        self._in_memory_access_token = access_token
        self._in_memory_refresh_token = refresh_token

        if keyring is not None:
            try:
                if access_token:
                    keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USER_ACCESS_TOKEN, access_token)
                if refresh_token:
                    keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USER_REFRESH_TOKEN, refresh_token)
            except Exception as e:
                log.warning(f"Failed writing tokens to OS Credential Store: {e}")

    def _clear_credentials(self) -> None:
        """Delete credentials from OS Credential Store and disk."""
        self._in_memory_access_token = None
        self._in_memory_refresh_token = None

        if keyring is not None:
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USER_ACCESS_TOKEN)
            except Exception:
                pass
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USER_REFRESH_TOKEN)
            except Exception:
                pass

        self.metadata = {}
        if self.session_file.exists():
            try:
                self.session_file.unlink()
            except Exception:
                pass

    @property
    def is_authenticated(self) -> bool:
        """Check if client currently has a valid session."""
        return bool(self._in_memory_access_token or self._in_memory_refresh_token)

    @property
    def user_id(self) -> Optional[str]:
        """Get the authenticated auth.users UUID."""
        return self.metadata.get("user_id")

    @property
    def user_email(self) -> Optional[str]:
        """Get the authenticated user email."""
        return self.metadata.get("email")

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in to Aachman Account with email and password."""
        url = f"{self.supabase_url}/auth/v1/token?grant_type=password"
        headers = {
            "apikey": self.supabase_key,
            "Content-Type": "application/json",
        }
        payload = {"email": email, "password": password}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                access_token = data.get("access_token")
                refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 3600)

                # Store sensitive tokens in OS Credential Manager
                self._save_credentials_to_keyring(access_token, refresh_token)

                # Store non-sensitive metadata in session file
                self.metadata = {
                    "user_id": user.get("id"),
                    "email": user.get("email"),
                    "expires_at": int(time.time()) + expires_in,
                }
                self._save_metadata()

                log.info(f"Successfully authenticated with Aachman Account as {email}")
                return {"success": True, "user": user}
            else:
                err_msg = resp.json().get("error_description") or resp.json().get("msg") or resp.text
                return {"success": False, "error": err_msg}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Connection timed out during sign in."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Ecosystem connection unavailable (offline mode)."}
        except Exception as e:
            log.error(f"Sign in failed: {e}")
            return {"success": False, "error": str(e)}

    def refresh_access_token(self) -> bool:
        """Refresh access token using stored refresh token and rotate credentials."""
        refresh_token = self._in_memory_refresh_token
        if not refresh_token:
            return False

        url = f"{self.supabase_url}/auth/v1/token?grant_type=refresh_token"
        headers = {
            "apikey": self.supabase_key,
            "Content-Type": "application/json",
        }
        payload = {"refresh_token": refresh_token}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token") or refresh_token
                expires_in = data.get("expires_in", 3600)

                # Update OS Credential Store with rotated tokens
                self._save_credentials_to_keyring(new_access_token, new_refresh_token)

                self.metadata["expires_at"] = int(time.time()) + expires_in
                self._save_metadata()
                log.info("Successfully refreshed and rotated Aachman Account session token.")
                return True
            else:
                log.warning("Refresh token revoked or invalid. Clearing expired credentials.")
                self._clear_credentials()
                return False
        except Exception as e:
            log.warning(f"Token refresh failed: {e}")
            return False

    def get_valid_access_token(self) -> Optional[str]:
        """Return valid access token, auto-refreshing if expired."""
        now = int(time.time())
        expires_at = self.metadata.get("expires_at", 0)

        # If token is within 60 seconds of expiring, refresh it
        if expires_at - now <= 60:
            if not self.refresh_access_token():
                return None

        return self._in_memory_access_token

    def sign_out(self) -> Dict[str, Any]:
        """Sign out from PyFlare session, delete stored OS credentials, and notify Supabase."""
        access_token = self._in_memory_access_token
        if access_token:
            url = f"{self.supabase_url}/auth/v1/logout"
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {access_token}",
            }
            try:
                requests.post(url, headers=headers, timeout=5)
            except Exception:
                pass

        self._clear_credentials()
        return {"success": True}

    def execute_ecosystem_action(
        self, action_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call the authoritative public.execute_ecosystem_action RPC.

        Identity is derived strictly server-side from auth.uid().
        """
        access_token = self.get_valid_access_token()
        if not access_token:
            return {
                "success": False,
                "error": "Authentication required. Please sign in to your Aachman Account first.",
            }

        url = f"{self.supabase_url}/rest/v1/rpc/execute_ecosystem_action"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "p_action_type": action_type,
            "p_payload": payload,
        }

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=12)
            if resp.status_code == 200:
                result = resp.json()
                return result
            elif resp.status_code in (401, 403):
                # Try one token refresh on 401
                if self.refresh_access_token():
                    refreshed_token = self._in_memory_access_token
                    headers["Authorization"] = f"Bearer {refreshed_token}"
                    retry_resp = requests.post(url, headers=headers, json=body, timeout=12)
                    if retry_resp.status_code == 200:
                        return retry_resp.json()

                return {
                    "success": False,
                    "error": "Session expired or invalid. Please sign in again.",
                }
            else:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    err_text = err_json.get("message") or err_json.get("hint") or err_text
                except Exception:
                    pass
                return {"success": False, "error": f"Server error: {err_text}"}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out connecting to Aachman ecosystem."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Ecosystem connection unavailable (offline mode)."}
        except Exception as e:
            return {"success": False, "error": f"Ecosystem request error: {str(e)}"}


# Global singleton client instance
_global_client: Optional[AachmanEcosystemClient] = None


def get_ecosystem_client() -> AachmanEcosystemClient:
    """Retrieve or initialize global Aachman ecosystem client."""
    global _global_client
    if _global_client is None:
        _global_client = AachmanEcosystemClient()
    return _global_client
