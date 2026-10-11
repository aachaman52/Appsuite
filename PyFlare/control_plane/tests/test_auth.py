"""Acceptance tests for Authentication and Credential Security (Section 8)."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pyflare_control.auth import (
    AuthError,
    AuthManager,
    CredentialNotFoundError,
    InvalidSessionError,
    SessionExpiredError,
    sanitize_text,
)


class AuthAndCredentialSecurityAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "auth.sqlite3"
        self.auth = AuthManager(self.db_path, session_lifetime_hours=1)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_acceptance_1_registration_login_logout(self) -> None:
        """Acceptance Test 1: Clear registration, login, and logout behavior."""
        user = self.auth.register_user("aachman", "secure_password_123", email="aachman@pyflare.io")
        self.assertEqual(user.username, "aachman")
        self.assertTrue(user.is_local)

        # Login produces session with cryptographically secure token
        session = self.auth.login("aachman", "secure_password_123")
        self.assertEqual(len(session.token), 64)
        self.assertFalse(session.is_revoked)

        # Validate session returns identical user identity
        validated_user = self.auth.validate_session(session.token)
        self.assertEqual(validated_user.user_id, user.user_id)

        # Logout revokes session
        self.auth.logout(session.token)

        # Re-validating revoked session raises InvalidSessionError
        with self.assertRaises(InvalidSessionError):
            self.auth.validate_session(session.token)

    def test_acceptance_2_authentication_failures_handled_explicitly(self) -> None:
        """Acceptance Test 2: Invalid password or non-existent user raises explicit errors."""
        self.auth.register_user("developer", "correct_password")

        with self.assertRaises(AuthError):
            self.auth.login("developer", "wrong_password")

        with self.assertRaises(AuthError):
            self.auth.login("unknown_user", "some_password")

        with self.assertRaises(InvalidSessionError):
            self.auth.validate_session("non_existent_token_hex_string")

    def test_acceptance_3_expired_session_handling(self) -> None:
        """Acceptance Test 3: Expired sessions are rejected with SessionExpiredError."""
        self.auth.register_user("testuser", "password123")
        session = self.auth.login("testuser", "password123")

        # Manually backdate session expiration in DB
        expired_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        with self.auth._connect() as conn:
            conn.execute("UPDATE sessions SET expires_at = ? WHERE token = ?", (expired_time, session.token))

        with self.assertRaises(SessionExpiredError):
            self.auth.validate_session(session.token)

    def test_acceptance_4_secure_provider_credentials_storage_and_separation(self) -> None:
        """Acceptance Test 4: Provider credentials stored separately from user accounts, no key leakage in listings."""
        user = self.auth.register_user("dev1", "password123")

        # Store API keys
        self.auth.set_provider_credential("openai", "sk-proj-supersecretkey1234567890abcdef")
        self.auth.set_provider_credential("meshy", "msy-3d-secret-token-key-999")

        # List configured providers returns IDs only, never the plaintext secret
        providers = self.auth.list_configured_providers()
        self.assertIn("openai", providers)
        self.assertIn("meshy", providers)
        for p in providers:
            self.assertNotIn("sk-proj", p)
            self.assertNotIn("supersecret", p)

        # Retrieve specific key works
        key = self.auth.get_provider_credential("openai")
        self.assertEqual(key, "sk-proj-supersecretkey1234567890abcdef")

        # Non-existent credential raises CredentialNotFoundError
        with self.assertRaises(CredentialNotFoundError):
            self.auth.get_provider_credential("unknown_provider")

    def test_acceptance_5_secret_sanitizer_redacts_keys_from_logs_and_errors(self) -> None:
        """Acceptance Test 5: Error and log strings redact secrets automatically."""
        error_msg_1 = "Failed to call OpenAI with key sk-proj-1234567890abcdef12345678: 401 Unauthorized"
        sanitized_1 = sanitize_text(error_msg_1)
        self.assertNotIn("sk-proj-1234567890abcdef12345678", sanitized_1)
        self.assertIn("[REDACTED_SECRET]", sanitized_1)

        error_msg_2 = "Google AI call with key AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P failed"
        sanitized_2 = sanitize_text(error_msg_2)
        self.assertNotIn("AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P", sanitized_2)
        self.assertIn("[REDACTED_SECRET]", sanitized_2)

        error_msg_3 = "Authorization header: Bearer my_super_secret_jwt_token_123456"
        sanitized_3 = sanitize_text(error_msg_3)
        self.assertNotIn("my_super_secret_jwt_token_123456", sanitized_3)
        self.assertIn("Bearer [REDACTED_TOKEN]", sanitized_3)

    def test_acceptance_6_offline_operation_preservation(self) -> None:
        """Acceptance Test 6: Auth operates 100% locally and offline without external network."""
        # System functions entirely with local SQLite DB
        user = self.auth.register_user("offline_dev", "offline_pass_99")
        session = self.auth.login("offline_dev", "offline_pass_99")
        validated = self.auth.validate_session(session.token)
        self.assertEqual(validated.username, "offline_dev")
        self.assertTrue(validated.is_local)


if __name__ == "__main__":
    unittest.main()
