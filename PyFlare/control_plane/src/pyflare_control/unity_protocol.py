"""Transport-neutral Unity bridge protocol contracts and state gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class EditorMode(StrEnum):
    EDIT = "edit"
    PLAY = "play"
    TRANSITIONING = "transitioning"


class OperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class UnityPreconditions:
    editor_mode: EditorMode = EditorMode.EDIT
    compilation_must_be_idle: bool = True
    scene_path: str | None = None
    scene_hash: str | None = None


@dataclass(frozen=True, slots=True)
class UnityCommand:
    protocol: str
    request_id: str
    task_id: str
    project_id: str
    operation: str
    arguments: Mapping[str, Any]
    preconditions: UnityPreconditions = field(default_factory=UnityPreconditions)
    idempotency_key: str = ""
    register_undo: bool = True
    save_scene: bool = False

    def __post_init__(self) -> None:
        if self.protocol != "pyflare-unity/1.0":
            raise ValueError("unsupported Unity protocol")
        for value, name in (
            (self.request_id, "request_id"),
            (self.task_id, "task_id"),
            (self.project_id, "project_id"),
            (self.operation, "operation"),
            (self.idempotency_key, "idempotency_key"),
        ):
            if not value:
                raise ValueError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class UnityEditorState:
    mode: EditorMode
    compiling: bool
    updating_assets: bool
    open_scene_path: str | None
    open_scene_hash: str | None


@dataclass(frozen=True, slots=True)
class UnityResponse:
    protocol: str
    request_id: str
    status: OperationStatus
    result: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class UnityStateGate:
    EDIT_ONLY_PREFIXES = (
        "scene.",
        "game_object.",
        "component.",
        "prefab.",
        "asset.",
        "project_settings.",
    )

    @classmethod
    def rejection_reasons(
        cls,
        command: UnityCommand,
        state: UnityEditorState,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        expected = command.preconditions
        if expected.compilation_must_be_idle and state.compiling:
            reasons.append("unity_compiling")
        if state.updating_assets:
            reasons.append("unity_asset_database_updating")
        if expected.editor_mode is not state.mode:
            reasons.append("editor_mode_mismatch")
        if (
            command.operation.startswith(cls.EDIT_ONLY_PREFIXES)
            and state.mode is not EditorMode.EDIT
        ):
            reasons.append("edit_only_operation_during_play_mode")
        if expected.scene_path and expected.scene_path != state.open_scene_path:
            reasons.append("scene_path_mismatch")
        if expected.scene_hash and expected.scene_hash != state.open_scene_hash:
            reasons.append("scene_hash_mismatch")
        return tuple(dict.fromkeys(reasons))
