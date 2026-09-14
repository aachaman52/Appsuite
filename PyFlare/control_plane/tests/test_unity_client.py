import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from pyflare_control.unity_client import (
    UnityBridgeClient,
    UnityBridgeConfig,
    UnityBridgeProtocolError,
    UnityBridgeSecurityError,
)
from pyflare_control.unity_protocol import OperationStatus, UnityCommand

TOKEN = "unit-test-token-with-at-least-32-characters"


class _BridgeHandler(BaseHTTPRequestHandler):
    received_token = ""
    received_payload: ClassVar[dict[str, object]] = {}

    def do_GET(self) -> None:
        self.__class__.received_token = self.headers.get("X-PyFlare-Token", "")
        if self.path != "/health":
            self.send_error(404)
            return
        self._send_json(
            {
                "protocol": "pyflare-unity/1.0",
                "status": "ready",
                "bridge_version": "test",
            }
        )

    def do_POST(self) -> None:
        self.__class__.received_token = self.headers.get("X-PyFlare-Token", "")
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.received_payload = payload
        if payload["operation"] == "test.large":
            self._send_json(
                {
                    "protocol": "pyflare-unity/1.0",
                    "request_id": payload["request_id"],
                    "status": "succeeded",
                    "result": {"padding": "x" * 4_096},
                    "errors": [],
                    "warnings": [],
                }
            )
            return
        request_id = (
            "wrong-request"
            if payload["operation"] == "test.mismatch"
            else payload["request_id"]
        )
        self._send_json(
            {
                "protocol": "pyflare-unity/1.0",
                "request_id": request_id,
                "status": "succeeded",
                "result": {"object_id": "GlobalObjectId_V1-test"},
                "errors": [],
                "warnings": [],
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class UnityBridgeClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.endpoint = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        _BridgeHandler.received_token = ""
        _BridgeHandler.received_payload = {}
        self.client = UnityBridgeClient(
            UnityBridgeConfig(endpoint=self.endpoint, token=TOKEN)
        )

    def test_health_is_authenticated(self) -> None:
        health = self.client.health()

        self.assertEqual(health["status"], "ready")
        self.assertEqual(_BridgeHandler.received_token, TOKEN)

    def test_execute_round_trip(self) -> None:
        response = self.client.execute(self._command("game_object.create"))

        self.assertEqual(response.status, OperationStatus.SUCCEEDED)
        self.assertEqual(response.result["object_id"], "GlobalObjectId_V1-test")
        self.assertEqual(_BridgeHandler.received_payload["arguments"], {"name": "Enemy"})
        self.assertEqual(
            _BridgeHandler.received_payload["preconditions"]["editor_mode"],
            "edit",
        )

    def test_mismatched_response_is_rejected(self) -> None:
        with self.assertRaises(UnityBridgeProtocolError):
            self.client.execute(self._command("test.mismatch"))

    def test_oversized_response_is_rejected(self) -> None:
        client = UnityBridgeClient(
            UnityBridgeConfig(
                endpoint=self.endpoint,
                token=TOKEN,
                max_response_bytes=1_024,
            )
        )
        with self.assertRaises(UnityBridgeProtocolError):
            client.execute(self._command("test.large"))

    def test_non_loopback_endpoint_is_rejected(self) -> None:
        with self.assertRaises(UnityBridgeSecurityError):
            UnityBridgeConfig(endpoint="http://example.com:47831", token=TOKEN)

    def test_short_token_is_rejected(self) -> None:
        with self.assertRaises(UnityBridgeSecurityError):
            UnityBridgeConfig(endpoint=self.endpoint, token="too-short")

    @staticmethod
    def _command(operation: str) -> UnityCommand:
        return UnityCommand(
            protocol="pyflare-unity/1.0",
            request_id="request-1",
            task_id="task-1",
            project_id="project-1",
            operation=operation,
            arguments={"name": "Enemy"},
            idempotency_key="task-1:game-object:create:enemy",
        )


if __name__ == "__main__":
    unittest.main()
