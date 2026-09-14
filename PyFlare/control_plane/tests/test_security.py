from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pyflare_control.models import Permission
from pyflare_control.security import PermissionGrant


class SecurityTests(unittest.TestCase):
    def test_path_scope_enforces_root_allowlist_and_denylist(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            grant = PermissionGrant(
                grant_id="grant",
                task_id="task",
                subject="worker",
                permissions=frozenset({Permission.READ, Permission.WRITE}),
                project_root=root,
                allowed_paths=("Assets/Scripts/Enemies/**",),
                denied_paths=("Assets/Scripts/Enemies/Secrets/**",),
                allowed_capabilities=frozenset({"code.csharp.modify"}),
            )
            self.assertTrue(
                grant.permits_path(
                    root / "Assets/Scripts/Enemies/Enemy.cs",
                    Permission.WRITE,
                )
            )
            self.assertFalse(
                grant.permits_path(
                    root / "Assets/Scripts/Player.cs",
                    Permission.WRITE,
                )
            )
            self.assertFalse(
                grant.permits_path(
                    root / "Assets/Scripts/Enemies/Secrets/key.txt",
                    Permission.WRITE,
                )
            )
            self.assertFalse(
                grant.permits_path(root.parent / "escape.txt", Permission.WRITE)
            )


if __name__ == "__main__":
    unittest.main()
