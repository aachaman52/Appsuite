"""Task-scoped authorization primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

from .models import Permission


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    grant_id: str
    task_id: str
    subject: str
    permissions: frozenset[Permission]
    project_root: Path
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...] = ()
    allowed_capabilities: frozenset[str] = frozenset()
    expires_at: datetime | None = None

    def is_expired(self, now: datetime | None = None) -> bool:
        instant = now or datetime.now(UTC)
        return self.expires_at is not None and instant >= self.expires_at

    def permits_capability(self, capability_id: str) -> bool:
        return not self.is_expired() and capability_id in self.allowed_capabilities

    def permits_path(self, candidate: Path, permission: Permission) -> bool:
        if self.is_expired() or permission not in self.permissions:
            return False

        root = self.project_root.resolve()
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            return False

        if any(fnmatch(relative, pattern) for pattern in self.denied_paths):
            return False
        return any(fnmatch(relative, pattern) for pattern in self.allowed_paths)


class AuthorizationError(PermissionError):
    pass


class Authorizer:
    @staticmethod
    def require_capability(grant: PermissionGrant, capability_id: str) -> None:
        if not grant.permits_capability(capability_id):
            raise AuthorizationError(
                f"grant {grant.grant_id} does not permit capability {capability_id}"
            )

    @staticmethod
    def require_path(
        grant: PermissionGrant,
        candidate: Path,
        permission: Permission,
    ) -> None:
        if not grant.permits_path(candidate, permission):
            raise AuthorizationError(
                f"grant {grant.grant_id} does not permit {permission} on {candidate}"
            )
