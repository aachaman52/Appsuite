from __future__ import annotations

import unittest

from pyflare_control.unity_protocol import (
    EditorMode,
    UnityCommand,
    UnityEditorState,
    UnityPreconditions,
    UnityStateGate,
)


class UnityProtocolTests(unittest.TestCase):
    def command(self) -> UnityCommand:
        return UnityCommand(
            protocol="pyflare-unity/1.0",
            request_id="request",
            task_id="task",
            project_id="project",
            operation="game_object.create",
            arguments={"name": "EnemySpawner"},
            preconditions=UnityPreconditions(
                editor_mode=EditorMode.EDIT,
                scene_path="Assets/Scenes/MainLevel.unity",
                scene_hash="sha256:expected",
            ),
            idempotency_key="task:step:attempt",
        )

    def test_accepts_matching_idle_editor(self) -> None:
        state = UnityEditorState(
            mode=EditorMode.EDIT,
            compiling=False,
            updating_assets=False,
            open_scene_path="Assets/Scenes/MainLevel.unity",
            open_scene_hash="sha256:expected",
        )
        self.assertEqual(UnityStateGate.rejection_reasons(self.command(), state), ())

    def test_rejects_stale_or_busy_editor(self) -> None:
        state = UnityEditorState(
            mode=EditorMode.PLAY,
            compiling=True,
            updating_assets=False,
            open_scene_path="Assets/Scenes/MainLevel.unity",
            open_scene_hash="sha256:changed",
        )
        reasons = UnityStateGate.rejection_reasons(self.command(), state)
        self.assertIn("unity_compiling", reasons)
        self.assertIn("editor_mode_mismatch", reasons)
        self.assertIn("edit_only_operation_during_play_mode", reasons)
        self.assertIn("scene_hash_mismatch", reasons)


if __name__ == "__main__":
    unittest.main()
