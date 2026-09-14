using System;

namespace AachmanStudios.PyFlare.Unity
{
    [Serializable]
    internal sealed class UnityCommandEnvelope
    {
        public string protocol;
        public string request_id;
        public string task_id;
        public string project_id;
        public string operation;
        public UnityArguments arguments;
        public UnityPreconditions preconditions;
        public string idempotency_key;
        public bool register_undo;
        public bool save_scene;
    }

    [Serializable]
    internal sealed class UnityArguments
    {
        public string name;
        public float[] position;
        public string parent_object_id;
    }

    [Serializable]
    internal sealed class UnityPreconditions
    {
        public string editor_mode;
        public bool compilation_must_be_idle;
        public string scene_path;
        public string scene_hash;
    }

    [Serializable]
    internal sealed class UnityResponseEnvelope
    {
        public string protocol = BridgeProtocol.Protocol;
        public string request_id;
        public string status;
        public UnityResult result = new UnityResult();
        public string[] errors = Array.Empty<string>();
        public string[] warnings = Array.Empty<string>();
    }

    [Serializable]
    internal sealed class UnityResult
    {
        public string object_id;
        public string name;
        public string scene_path;
        public UnityEditorStatePayload editor_state;
    }

    [Serializable]
    internal sealed class UnityEditorStatePayload
    {
        public string mode;
        public bool compiling;
        public bool updating_assets;
        public string open_scene_path;
        public string open_scene_hash;
    }

    [Serializable]
    internal sealed class HealthResponse
    {
        public string protocol = BridgeProtocol.Protocol;
        public string status = "ready";
        public string bridge_version = BridgeProtocol.BridgeVersion;
    }

    [Serializable]
    internal sealed class IdempotencyRecord
    {
        public string request_fingerprint;
        public string response_json;
    }

    internal static class BridgeProtocol
    {
        internal const string Protocol = "pyflare-unity/1.0";
        internal const string BridgeVersion = "0.1.0-experimental";
    }
}
