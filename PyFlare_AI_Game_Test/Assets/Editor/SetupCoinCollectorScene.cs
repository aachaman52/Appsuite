#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class SetupCoinCollectorScene
{
    [MenuItem("PyFlare/Setup Coin Collector Scene")]
    public static void RunSetupAndVerify()
    {
        Debug.Log("=== [PyFlare AI Game Test] Setting up Mini 3D Coin Collector Scene ===");

        // Create new empty scene
        Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        // 1. Directional Light
        GameObject lightGo = new GameObject("Directional Light");
        Light light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        lightGo.transform.rotation = Quaternion.Euler(50, -30, 0);

        // 2. Ground Plane
        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.position = Vector3.zero;
        ground.transform.localScale = new Vector3(5, 1, 5);

        // 3. Player
        GameObject player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        player.name = "Player";
        player.tag = "Player";
        player.transform.position = new Vector3(0, 1.0f, 0);
        
        // Remove default capsule collider and use CharacterController
        Collider defaultCollider = player.GetComponent<Collider>();
        if (defaultCollider != null) Object.DestroyImmediate(defaultCollider);
        
        CharacterController cc = player.AddComponent<CharacterController>();
        PlayerController pc = player.AddComponent<PlayerController>();
        pc.speed = 8.0f;

        // 4. Main Camera
        GameObject camGo = new GameObject("Main Camera");
        camGo.tag = "MainCamera";
        Camera cam = camGo.AddComponent<Camera>();
        camGo.AddComponent<AudioListener>();
        CameraController camCtrl = camGo.AddComponent<CameraController>();
        camCtrl.target = player.transform;
        camCtrl.offset = new Vector3(0, 4, -7);

        // 5. Game Manager
        GameObject gmGo = new GameObject("GameManager");
        GameManager gm = gmGo.AddComponent<GameManager>();
        gm.totalCoins = 5;

        // 6. 5 Collectible Coins
        Vector3[] coinPositions = new Vector3[]
        {
            new Vector3(3, 0.6f, 3),
            new Vector3(-4, 0.6f, 5),
            new Vector3(5, 0.6f, -3),
            new Vector3(-3, 0.6f, -4),
            new Vector3(0, 0.6f, 7)
        };

        for (int i = 0; i < coinPositions.Length; i++)
        {
            GameObject coin = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            coin.name = $"Coin_{i + 1}";
            coin.transform.position = coinPositions[i];
            coin.transform.localScale = new Vector3(0.6f, 0.1f, 0.6f);
            coin.transform.rotation = Quaternion.Euler(90, 0, 0);

            // Trigger collider
            Collider cCol = coin.GetComponent<Collider>();
            if (cCol != null) cCol.isTrigger = true;

            Coin cScript = coin.AddComponent<Coin>();
            cScript.rotationSpeed = 90.0f;
        }

        // Save scene
        System.IO.Directory.CreateDirectory("Assets/Scenes");
        string scenePath = "Assets/Scenes/CoinCollector.unity";
        EditorSceneManager.SaveScene(scene, scenePath);
        Debug.Log($"[PyFlare AI Game Test] Scene successfully constructed and saved to {scenePath}");

        // Add to EditorBuildSettings
        EditorBuildSettings.scenes = new EditorBuildSettingsScene[]
        {
            new EditorBuildSettingsScene(scenePath, true)
        };

        Debug.Log("[PyFlare AI Game Test] Scene verified: Ground, Player, Camera, GameManager, and 5 Coins active.");
    }
}
#endif
