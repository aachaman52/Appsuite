# PyFlare Unity Automation

Status: **experimental foundation; not production-ready**.

This Unity Package Manager package implements the first narrow structured bridge between
the PyFlare control plane and the Unity Editor. It targets Unity 6 (6000.0 minimum in
the package manifest). It has not yet been compiled inside Unity in CI, so Unity-version
compatibility requires explicit editor benchmarking and validation.

## Implemented operations

| Operation | Behavior | Disk persistence |
| --- | --- | --- |
| editor.state.inspect | Returns edit/play/transition state, compilation state, Asset Database update state, active scene path and saved scene hash | None |
| game_object.create | Creates one GameObject, optional world position and optional parent by Unity GlobalObjectId | Marks scene dirty; does not save |

The bridge intentionally rejects save_scene: true in version 0.1. This makes the first
mutation visible and undoable before it is written to disk. Component changes, prefabs,
imports, tests, builds and console inspection remain planned operations.

## Install for development

In Unity Package Manager, choose **Add package from disk** and select this package's
package.json. A production installer should later pin the package by verified version
and hash.

Set a random token of at least 32 characters in the environment that launches Unity:

    PYFLARE_UNITY_BRIDGE_TOKEN=<secret>
    PYFLARE_UNITY_BRIDGE_ENABLED=1

If automatic startup is disabled, use **Tools > PyFlare > Unity Bridge > Start**. The
token is never stored in the Unity project. PyFlare should obtain it from the OS secret
service and inject it only into the Unity process and authorized worker.

## Transport contract

- Endpoint: http://127.0.0.1:47831
- Health: authenticated GET /health
- Commands: authenticated POST /v1/commands
- Authentication header: X-PyFlare-Token
- Request body maximum: 1 MiB
- Protocol: pyflare-unity/1.0
- Queue capacity: 128 requests
- Main-thread dispatch: at most 8 requests per editor update
- Queue timeout: 8 seconds
- Idempotency records: Unity project's Library/PyFlare/UnityBridge/idempotency

The listener accepts only loopback clients. It does not enable CORS, expose a remote
socket or put credentials into URLs. The listener thread performs transport work only;
Unity APIs execute through EditorApplication.update on the editor main thread.

## Example

    {
      "protocol": "pyflare-unity/1.0",
      "request_id": "request-142",
      "task_id": "unity-142",
      "project_id": "sample-game",
      "operation": "game_object.create",
      "arguments": {
        "name": "EnemySpawner",
        "position": [0, 0, 0],
        "parent_object_id": ""
      },
      "preconditions": {
        "editor_mode": "edit",
        "compilation_must_be_idle": true,
        "scene_path": "Assets/Scenes/MainLevel.unity",
        "scene_hash": "sha256:..."
      },
      "idempotency_key": "unity-142:create:enemy-spawner",
      "register_undo": true,
      "save_scene": false
    }

## Safety boundaries

- A valid route does not authorize this bridge. The control plane must separately issue
  task-scoped permissions before sending a command.
- Mutating v0.1 commands require Unity Undo registration.
- A repeated idempotency key with a different payload is rejected.
- Stored idempotency data contains responses and fingerprints, not the authentication
  token, and lives under the disposable Unity Library directory.
- The bridge returns stable error codes and does not send exception details to clients.
- Stopping the bridge closes queued requests instead of silently executing them later.
- The first release must be tested on the exact supported Unity editor versions and
  Ubuntu image before its status can move beyond experimental.
