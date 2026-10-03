using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace AachmanStudios.PyFlare.Unity
{
    [InitializeOnLoad]
    internal static class PyFlareUnityBridge
    {
        private const string Prefix = "http://127.0.0.1:47831/";
        private const string TokenHeader = "X-PyFlare-Token";
        private const int MaximumQueuedRequests = 128;
        private const int MaximumRequestsPerEditorUpdate = 8;
        private const double QueueTimeoutSeconds = 8.0;

        private static readonly ConcurrentQueue<PendingRequest> PendingRequests =
            new ConcurrentQueue<PendingRequest>();

        private static HttpListener listener;
        private static CancellationTokenSource cancellation;
        private static Task listenerTask;
        private static string token;
        private static int queuedRequestCount;

        static PyFlareUnityBridge()
        {
            EditorApplication.update += DrainRequestQueue;
            AssemblyReloadEvents.beforeAssemblyReload += Stop;
            EditorApplication.quitting += Stop;

            if (Environment.GetEnvironmentVariable("PYFLARE_UNITY_BRIDGE_ENABLED") == "1")
            {
                EditorApplication.delayCall += Start;
            }
        }

        [MenuItem("Tools/PyFlare/Unity Bridge/Start")]
        private static void StartFromMenu()
        {
            Start();
        }

        [MenuItem("Tools/PyFlare/Unity Bridge/Start", true)]
        private static bool CanStartFromMenu()
        {
            return listener == null;
        }

        [MenuItem("Tools/PyFlare/Unity Bridge/Stop")]
        private static void StopFromMenu()
        {
            Stop();
        }

        [MenuItem("Tools/PyFlare/Unity Bridge/Stop", true)]
        private static bool CanStopFromMenu()
        {
            return listener != null;
        }

        [MenuItem("Tools/PyFlare/Unity Bridge/Status")]
        private static void LogStatus()
        {
            Debug.Log(
                listener == null
                    ? "PyFlare Unity Bridge is stopped."
                    : "PyFlare Unity Bridge is listening on loopback."
            );
        }

        private static void Start()
        {
            if (listener != null)
            {
                return;
            }

            var configuredToken =
                Environment.GetEnvironmentVariable("PYFLARE_UNITY_BRIDGE_TOKEN");
            if (string.IsNullOrEmpty(configuredToken) || configuredToken.Length < 32)
            {
                Debug.LogError(
                    "PyFlare Unity Bridge did not start: " +
                    "PYFLARE_UNITY_BRIDGE_TOKEN must contain at least 32 characters."
                );
                return;
            }

            var newListener = new HttpListener();
            newListener.Prefixes.Add(Prefix);

            try
            {
                newListener.Start();
            }
            catch (Exception exception)
            {
                newListener.Close();
                Debug.LogError(
                    "PyFlare Unity Bridge could not bind its loopback endpoint: " +
                    exception.GetType().Name
                );
                return;
            }

            token = configuredToken;
            cancellation = new CancellationTokenSource();
            listener = newListener;
            listenerTask = Task.Run(
                () => ListenLoop(newListener, cancellation.Token),
                cancellation.Token
            );
            Debug.Log("PyFlare Unity Bridge started on http://127.0.0.1:47831.");
        }

        private static void Stop()
        {
            var activeListener = listener;
            listener = null;
            token = null;

            if (cancellation != null)
            {
                cancellation.Cancel();
                cancellation.Dispose();
                cancellation = null;
            }

            if (activeListener != null)
            {
                try
                {
                    activeListener.Stop();
                    activeListener.Close();
                }
                catch (ObjectDisposedException)
                {
                    // Already stopped during domain reload.
                }
            }

            listenerTask = null;
            while (PendingRequests.TryDequeue(out var pending))
            {
                Interlocked.Decrement(ref queuedRequestCount);
                WriteSimpleError(pending.Context, 503, "bridge_stopping");
            }
        }

        private static void ListenLoop(
            HttpListener activeListener,
            CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested && activeListener.IsListening)
            {
                HttpListenerContext context;
                try
                {
                    context = activeListener.GetContext();
                }
                catch (HttpListenerException)
                {
                    return;
                }
                catch (ObjectDisposedException)
                {
                    return;
                }

                Task.Run(() => AcceptRequest(context));
            }
        }

        private static void AcceptRequest(HttpListenerContext context)
        {
            try
            {
                if (!BridgeSecurity.IsLoopback(context.Request))
                {
                    WriteSimpleError(context, 403, "loopback_required");
                    return;
                }

                var suppliedToken = context.Request.Headers[TokenHeader];
                if (!BridgeSecurity.TokenEquals(token, suppliedToken))
                {
                    WriteSimpleError(context, 401, "unauthorized");
                    return;
                }

                var path = context.Request.Url == null
                    ? string.Empty
                    : context.Request.Url.AbsolutePath;
                if (context.Request.HttpMethod == "GET" && path == "/health")
                {
                    WriteJson(
                        context,
                        200,
                        "{\"protocol\":\"pyflare-unity/1.0\"," +
                        "\"status\":\"ready\"," +
                        "\"bridge_version\":\"0.1.0-experimental\"}"
                    );
                    return;
                }

                if (context.Request.HttpMethod != "POST" || path != "/v1/commands")
                {
                    WriteSimpleError(context, 404, "route_not_found");
                    return;
                }

                var contentType = context.Request.ContentType ?? string.Empty;
                if (!contentType.StartsWith(
                        "application/json",
                        StringComparison.OrdinalIgnoreCase))
                {
                    WriteSimpleError(context, 415, "json_required");
                    return;
                }

                string body;
                try
                {
                    body = BridgeSecurity.ReadBody(context.Request);
                }
                catch (InvalidDataException)
                {
                    WriteSimpleError(context, 413, "request_too_large");
                    return;
                }

                if (Interlocked.Increment(ref queuedRequestCount) >
                    MaximumQueuedRequests)
                {
                    Interlocked.Decrement(ref queuedRequestCount);
                    WriteSimpleError(context, 429, "bridge_queue_full");
                    return;
                }

                PendingRequests.Enqueue(
                    new PendingRequest(context, body, DateTime.UtcNow)
                );
            }
            catch (Exception)
            {
                WriteSimpleError(context, 500, "transport_failure");
            }
        }

        private static void DrainRequestQueue()
        {
            for (var index = 0; index < MaximumRequestsPerEditorUpdate; index++)
            {
                if (!PendingRequests.TryDequeue(out var pending))
                {
                    return;
                }

                Interlocked.Decrement(ref queuedRequestCount);
                ProcessOnMainThread(pending);
            }
        }

        private static void ProcessOnMainThread(PendingRequest pending)
        {
            UnityCommandEnvelope command;
            try
            {
                command = JsonUtility.FromJson<UnityCommandEnvelope>(pending.Body);
            }
            catch (ArgumentException)
            {
                WriteSimpleError(pending.Context, 400, "invalid_json");
                return;
            }

            if (command == null)
            {
                WriteSimpleError(pending.Context, 400, "invalid_command");
                return;
            }

            var validationError = ValidateEnvelope(command);
            if (validationError != null)
            {
                WriteCommandResponse(
                    pending.Context,
                    Rejected(command.request_id, validationError)
                );
                return;
            }

            if ((DateTime.UtcNow - pending.EnqueuedAtUtc).TotalSeconds >
                QueueTimeoutSeconds)
            {
                WriteCommandResponse(
                    pending.Context,
                    Response(command.request_id, "timed_out", "editor_queue_timeout")
                );
                return;
            }

            var fingerprint = BridgeIdempotencyStore.Fingerprint(pending.Body);
            try
            {
                if (BridgeIdempotencyStore.TryRead(
                        command.idempotency_key,
                        fingerprint,
                        out var cachedResponse,
                        out var conflict))
                {
                    WriteJson(pending.Context, 200, cachedResponse);
                    return;
                }

                if (conflict)
                {
                    WriteCommandResponse(
                        pending.Context,
                        Rejected(command.request_id, "idempotency_key_conflict")
                    );
                    return;
                }

                var response = ExecuteCommand(command);
                var responseJson = JsonUtility.ToJson(response);
                BridgeIdempotencyStore.Write(
                    command.idempotency_key,
                    fingerprint,
                    responseJson
                );
                WriteJson(pending.Context, 200, responseJson);
            }
            catch (Exception exception)
            {
                Debug.LogError(
                    "PyFlare Unity operation failed: " + exception.GetType().Name
                );
                WriteCommandResponse(
                    pending.Context,
                    Response(command.request_id, "failed", "internal_error")
                );
            }
        }

        private static UnityResponseEnvelope ExecuteCommand(
            UnityCommandEnvelope command)
        {
            switch (command.operation)
            {
                case "editor.state.inspect":
                    return new UnityResponseEnvelope
                    {
                        request_id = command.request_id,
                        status = "succeeded",
                        result = new UnityResult
                        {
                            editor_state = CaptureEditorState(),
                            scene_path = SceneManager.GetActiveScene().path
                        }
                    };
                case "game_object.create":
                    return CreateGameObject(command);
                default:
                    return Rejected(command.request_id, "unsupported_operation");
            }
        }

        private static UnityResponseEnvelope CreateGameObject(
            UnityCommandEnvelope command)
        {
            var gateError = StateGateError(command);
            if (gateError != null)
            {
                return Rejected(command.request_id, gateError);
            }

            if (!command.register_undo)
            {
                return Rejected(command.request_id, "undo_registration_required");
            }

            if (command.save_scene)
            {
                return Rejected(
                    command.request_id,
                    "save_scene_not_supported_in_bridge_v0_1"
                );
            }

            var activeSceneState = CaptureEditorState();
            if (string.IsNullOrEmpty(activeSceneState.open_scene_path) ||
                string.IsNullOrEmpty(activeSceneState.open_scene_hash))
            {
                return Rejected(
                    command.request_id,
                    "active_scene_must_be_saved_once"
                );
            }

            var arguments = command.arguments ?? new UnityArguments();
            var objectName = (arguments.name ?? string.Empty).Trim();
            if (objectName.Length == 0 || objectName.Length > 256)
            {
                return Rejected(command.request_id, "invalid_game_object_name");
            }

            var position = Vector3.zero;
            if (arguments.position != null)
            {
                if (arguments.position.Length != 3 ||
                    !IsFinite(arguments.position[0]) ||
                    !IsFinite(arguments.position[1]) ||
                    !IsFinite(arguments.position[2]))
                {
                    return Rejected(command.request_id, "invalid_position");
                }

                position = new Vector3(
                    arguments.position[0],
                    arguments.position[1],
                    arguments.position[2]
                );
            }

            Transform parent = null;
            if (!string.IsNullOrEmpty(arguments.parent_object_id))
            {
                if (!GlobalObjectId.TryParse(
                        arguments.parent_object_id,
                        out var parentId))
                {
                    return Rejected(command.request_id, "invalid_parent_object_id");
                }

                var parentObject =
                    GlobalObjectId.GlobalObjectIdentifierToObjectSlow(parentId);
                parent = ObjectTransform(parentObject);
                if (parent == null)
                {
                    return Rejected(command.request_id, "parent_object_not_found");
                }

                if (parent.gameObject.scene != SceneManager.GetActiveScene())
                {
                    return Rejected(command.request_id, "parent_scene_mismatch");
                }
            }

            Undo.IncrementCurrentGroup();
            var undoGroup = Undo.GetCurrentGroup();
            Undo.SetCurrentGroupName("PyFlare: Create " + objectName);

            try
            {
                var gameObject = new GameObject(objectName);
                Undo.RegisterCreatedObjectUndo(
                    gameObject,
                    "PyFlare: Create " + objectName
                );
                if (parent != null)
                {
                    Undo.SetTransformParent(
                        gameObject.transform,
                        parent,
                        "PyFlare: Parent " + objectName
                    );
                }

                Undo.RegisterFullObjectHierarchyUndo(
                    gameObject,
                    "PyFlare: Configure " + objectName
                );
                gameObject.transform.position = position;
                EditorSceneManager.MarkSceneDirty(gameObject.scene);
                Undo.CollapseUndoOperations(undoGroup);

                var globalId =
                    GlobalObjectId.GetGlobalObjectIdSlow(gameObject).ToString();
                return new UnityResponseEnvelope
                {
                    request_id = command.request_id,
                    status = "succeeded",
                    result = new UnityResult
                    {
                        object_id = globalId,
                        name = gameObject.name,
                        scene_path = gameObject.scene.path,
                        editor_state = CaptureEditorState()
                    },
                    warnings = new[] { "scene_modified_but_not_saved" }
                };
            }
            catch
            {
                Undo.RevertAllDownToGroup(undoGroup);
                throw;
            }
        }

        private static string StateGateError(UnityCommandEnvelope command)
        {
            var state = CaptureEditorState();
            var expected = command.preconditions ?? new UnityPreconditions();

            if (expected.compilation_must_be_idle && state.compiling)
            {
                return "unity_compiling";
            }

            if (state.updating_assets)
            {
                return "unity_asset_database_updating";
            }

            var expectedMode = string.IsNullOrEmpty(expected.editor_mode)
                ? "edit"
                : expected.editor_mode;
            if (!string.Equals(expectedMode, state.mode, StringComparison.Ordinal))
            {
                return "editor_mode_mismatch";
            }

            if (!string.IsNullOrEmpty(expected.scene_path) &&
                !string.Equals(
                    expected.scene_path,
                    state.open_scene_path,
                    StringComparison.Ordinal))
            {
                return "scene_path_mismatch";
            }

            if (!string.IsNullOrEmpty(expected.scene_hash) &&
                !string.Equals(
                    expected.scene_hash,
                    state.open_scene_hash,
                    StringComparison.Ordinal))
            {
                return "scene_hash_mismatch";
            }

            return null;
        }

        private static UnityEditorStatePayload CaptureEditorState()
        {
            var scene = SceneManager.GetActiveScene();
            var mode = EditorApplication.isPlaying
                ? "play"
                : EditorApplication.isPlayingOrWillChangePlaymode
                    ? "transitioning"
                    : "edit";

            return new UnityEditorStatePayload
            {
                mode = mode,
                compiling = EditorApplication.isCompiling,
                updating_assets = EditorApplication.isUpdating,
                open_scene_path = scene.path,
                open_scene_hash = SceneHash(scene.path)
            };
        }

        private static string SceneHash(string scenePath)
        {
            if (string.IsNullOrEmpty(scenePath))
            {
                return null;
            }

            var projectRoot = Directory.GetParent(Application.dataPath).FullName;
            var absolutePath = Path.Combine(
                projectRoot,
                scenePath.Replace('/', Path.DirectorySeparatorChar)
            );
            if (!File.Exists(absolutePath))
            {
                return null;
            }

            using (var stream = File.OpenRead(absolutePath))
            using (var sha256 = SHA256.Create())
            {
                var hash = sha256.ComputeHash(stream);
                var builder = new StringBuilder(hash.Length * 2);
                foreach (var value in hash)
                {
                    builder.Append(value.ToString("x2"));
                }

                return "sha256:" + builder;
            }
        }

        private static Transform ObjectTransform(Object value)
        {
            if (value is GameObject gameObject)
            {
                return gameObject.transform;
            }

            if (value is Component component)
            {
                return component.transform;
            }

            return null;
        }

        private static bool IsFinite(float value)
        {
            return !float.IsNaN(value) && !float.IsInfinity(value);
        }

        private static string ValidateEnvelope(UnityCommandEnvelope command)
        {
            if (command.protocol != BridgeProtocol.Protocol)
            {
                return "unsupported_protocol";
            }

            if (Missing(command.request_id) ||
                Missing(command.task_id) ||
                Missing(command.project_id) ||
                Missing(command.operation) ||
                Missing(command.idempotency_key))
            {
                return "required_field_missing";
            }

            if (command.request_id.Length > 256 ||
                command.task_id.Length > 256 ||
                command.project_id.Length > 256 ||
                command.operation.Length > 256 ||
                command.idempotency_key.Length > 512)
            {
                return "field_too_long";
            }

            return null;
        }

        private static bool Missing(string value)
        {
            return string.IsNullOrWhiteSpace(value);
        }

        private static UnityResponseEnvelope Rejected(
            string requestId,
            string error)
        {
            return Response(requestId, "rejected", error);
        }

        private static UnityResponseEnvelope Response(
            string requestId,
            string status,
            string error)
        {
            return new UnityResponseEnvelope
            {
                request_id = requestId ?? string.Empty,
                status = status,
                errors = new[] { error }
            };
        }

        private static void WriteCommandResponse(
            HttpListenerContext context,
            UnityResponseEnvelope response)
        {
            WriteJson(context, 200, JsonUtility.ToJson(response));
        }

        private static void WriteSimpleError(
            HttpListenerContext context,
            int statusCode,
            string error)
        {
            var escaped = error.Replace("\\", "\\\\").Replace("\"", "\\\"");
            WriteJson(context, statusCode, "{\"error\":\"" + escaped + "\"}");
        }

        private static void WriteJson(
            HttpListenerContext context,
            int statusCode,
            string json)
        {
            if (context == null)
            {
                return;
            }

            try
            {
                var bytes = Encoding.UTF8.GetBytes(json);
                context.Response.StatusCode = statusCode;
                context.Response.ContentType = "application/json; charset=utf-8";
                context.Response.ContentLength64 = bytes.Length;
                context.Response.Headers["Cache-Control"] = "no-store";
                context.Response.OutputStream.Write(bytes, 0, bytes.Length);
                context.Response.OutputStream.Close();
            }
            catch (Exception)
            {
                try
                {
                    context.Response.Close();
                }
                catch (Exception)
                {
                    // Client disconnected or listener was already disposed.
                }
            }
        }

        private sealed class PendingRequest
        {
            internal PendingRequest(
                HttpListenerContext context,
                string body,
                DateTime enqueuedAtUtc)
            {
                Context = context;
                Body = body;
                EnqueuedAtUtc = enqueuedAtUtc;
            }

            internal HttpListenerContext Context { get; }
            internal string Body { get; }
            internal DateTime EnqueuedAtUtc { get; }
        }
    }
}
