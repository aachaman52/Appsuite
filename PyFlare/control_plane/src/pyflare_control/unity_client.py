"""Authenticated loopback client for the PyFlare Unity Editor bridge."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .unity_protocol import (
    OperationStatus,
    UnityCommand,
    UnityResponse,
)


class UnityBridgeError(RuntimeError):
    """Base class for bridge failures that are safe for retry policy classification."""


class UnityBridgeSecurityError(UnityBridgeError):
    """Raised when endpoint or credentials violate the local transport policy."""


class UnityBridgeTransportError(UnityBridgeError):
    """Raised when the editor bridge cannot be reached or returns an HTTP error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UnityBridgeProtocolError(UnityBridgeError):
    """Raised when a response does not satisfy the bridge contract."""


@dataclass(frozen=True, slots=True)
class UnityBridgeConfig:
    endpoint: str = "http://127.0.0.1:47831"
    token: str = ""
    timeout_seconds: float = 10.0
    max_response_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "http":
            raise UnityBridgeSecurityError("Unity bridge endpoint must use local HTTP")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise UnityBridgeSecurityError("Unity bridge endpoint must be loopback-only")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise UnityBridgeSecurityError("Unity bridge endpoint contains forbidden URL parts")
        if parsed.path not in {"", "/"}:
            raise UnityBridgeSecurityError("Unity bridge endpoint must not contain a path")
        try:
            port = parsed.port
        except ValueError as exc:
            raise UnityBridgeSecurityError("Unity bridge endpoint has an invalid port") from exc
        if port is None:
            raise UnityBridgeSecurityError("Unity bridge endpoint requires an explicit port")
        if len(self.token) < 32:
            raise UnityBridgeSecurityError("Unity bridge token must contain at least 32 characters")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_bytes < 1_024:
            raise ValueError("max_response_bytes must be at least 1024")
        object.__setattr__(self, "endpoint", self.endpoint.rstrip("/"))


class UnityBridgeClient:
    """Thin transport client; orchestration, authorization and retries stay outside it."""

    def __init__(self, config: UnityBridgeConfig) -> None:
        self._config = config

    def health(self) -> Mapping[str, Any]:
        payload = self._request("GET", "/health", None)
        protocol = payload.get("protocol")
        if protocol != "pyflare-unity/1.0":
            raise UnityBridgeProtocolError("health response has an unsupported protocol")
        return MappingProxyType(dict(payload))

    def execute(self, command: UnityCommand) -> UnityResponse:
        payload = {
            "protocol": command.protocol,
            "request_id": command.request_id,
            "task_id": command.task_id,
            "project_id": command.project_id,
            "operation": command.operation,
            "arguments": dict(command.arguments),
            "preconditions": {
                "editor_mode": command.preconditions.editor_mode.value,
                "compilation_must_be_idle": (
                    command.preconditions.compilation_must_be_idle
                ),
                "scene_path": command.preconditions.scene_path,
                "scene_hash": command.preconditions.scene_hash,
            },
            "idempotency_key": command.idempotency_key,
            "register_undo": command.register_undo,
            "save_scene": command.save_scene,
        }
        response_payload = self._request("POST", "/v1/commands", payload)
        response = self._parse_response(response_payload)
        if response.request_id != command.request_id:
            raise UnityBridgeProtocolError("Unity response request_id does not match request")
        return response

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        data: bytes | None = None
        if payload is not None:
            try:
                data = json.dumps(
                    payload,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise UnityBridgeProtocolError(
                    "Unity command is not valid finite JSON"
                ) from exc

        request = Request(
            f"{self._config.endpoint}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-PyFlare-Token": self._config.token,
            },
        )
        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                declared_length = response.headers.get("Content-Length")
                if (
                    declared_length is not None
                    and int(declared_length) > self._config.max_response_bytes
                ):
                    raise UnityBridgeProtocolError("Unity response exceeds size limit")
                body = response.read(self._config.max_response_bytes + 1)
        except HTTPError as exc:
            if exc.code == 401:
                raise UnityBridgeSecurityError("Unity bridge rejected authentication") from exc
            raise UnityBridgeTransportError(
                f"Unity bridge returned HTTP {exc.code}",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise UnityBridgeTransportError("Unity bridge transport failed") from exc
        except ValueError as exc:
            raise UnityBridgeProtocolError("Unity response length is invalid") from exc

        if len(body) > self._config.max_response_bytes:
            raise UnityBridgeProtocolError("Unity response exceeds size limit")
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnityBridgeProtocolError("Unity bridge returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise UnityBridgeProtocolError("Unity bridge response must be a JSON object")
        return decoded

    @staticmethod
    def _parse_response(payload: Mapping[str, Any]) -> UnityResponse:
        if payload.get("protocol") != "pyflare-unity/1.0":
            raise UnityBridgeProtocolError("Unity response has an unsupported protocol")
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise UnityBridgeProtocolError("Unity response request_id is required")
        try:
            status = OperationStatus(payload.get("status"))
        except (TypeError, ValueError) as exc:
            raise UnityBridgeProtocolError("Unity response status is invalid") from exc
        result = payload.get("result", {})
        if not isinstance(result, dict):
            raise UnityBridgeProtocolError("Unity response result must be an object")
        errors = UnityBridgeClient._string_tuple(payload.get("errors", []), "errors")
        warnings = UnityBridgeClient._string_tuple(
            payload.get("warnings", []),
            "warnings",
        )
        return UnityResponse(
            protocol="pyflare-unity/1.0",
            request_id=request_id,
            status=status,
            result=MappingProxyType(dict(result)),
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise UnityBridgeProtocolError(
                f"Unity response {field_name} must be a string array"
            )
        return tuple(value)
