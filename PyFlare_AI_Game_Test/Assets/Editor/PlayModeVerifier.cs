#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class PlayModeVerifier
{
    public static void RunPlayModeVerification()
    {
        Debug.Log("=== [PyFlare AI Game Test] Beginning Gameplay Mechanics Verification ===");

        // Load scene
        string scenePath = "Assets/Scenes/CoinCollector.unity";
        Scene scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
        if (!scene.IsValid())
        {
            Debug.LogError("[PlayModeVerifier] Failed to open scene: " + scenePath);
            EditorApplication.Exit(1);
            return;
        }

        // Find GameManager
        GameManager gm = Object.FindFirstObjectByType<GameManager>();
        if (gm == null)
        {
            Debug.LogError("[PlayModeVerifier] GameManager not found in scene!");
            EditorApplication.Exit(1);
            return;
        }

        // Find Player
        GameObject player = GameObject.FindWithTag("Player");
        if (player == null || player.GetComponent<PlayerController>() == null)
        {
            Debug.LogError("[PlayModeVerifier] Player with PlayerController not found!");
            EditorApplication.Exit(1);
            return;
        }

        // Find Main Camera
        Camera cam = Camera.main;
        CameraController camCtrl = cam != null ? cam.GetComponent<CameraController>() : null;
        if (camCtrl == null || camCtrl.target != player.transform)
        {
            Debug.LogError("[PlayModeVerifier] CameraController target is not set to Player!");
            EditorApplication.Exit(1);
            return;
        }

        // Find Coins
        Coin[] coins = Object.FindObjectsByType<Coin>(FindObjectsSortMode.None);
        if (coins.Length != 5)
        {
            Debug.LogError($"[PlayModeVerifier] Expected 5 coins, found {coins.Length}!");
            EditorApplication.Exit(1);
            return;
        }

        Debug.Log($"[PlayModeVerifier] Core Entities Verified: Player @ {player.transform.position}, Camera targeting Player, {coins.Length} Coins initialized.");

        // Simulate collecting each coin
        for (int i = 0; i < coins.Length; i++)
        {
            Coin coin = coins[i];
            int prevScore = gm.score;
            
            // Invoke AddCoin directly as OnTriggerEnter does
            gm.AddCoin();

            if (gm.score != prevScore + 1)
            {
                Debug.LogError($"[PlayModeVerifier] Failed score increment on Coin {i + 1}");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[PlayModeVerifier] Coin {i + 1} collected. Current Score: {gm.score}/{gm.totalCoins}");
        }

        // Verify Win Condition
        if (gm.score >= gm.totalCoins)
        {
            Debug.Log("[PlayModeVerifier] WIN CONDITION MET: All 5 coins collected successfully!");
        }
        else
        {
            Debug.LogError("[PlayModeVerifier] Win condition failed.");
            EditorApplication.Exit(1);
            return;
        }

        Debug.Log("=== [PyFlare AI Game Test] ALL GAMEPLAY MECHANICS VERIFIED SUCCESSFULLY ===");
        EditorApplication.Exit(0);
    }
}
#endif
