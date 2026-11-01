using UnityEngine;
using UnityEngine.SceneManagement;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance;

    public int score = 0;
    public int totalCoins = 5;

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public void AddCoin()
    {
        score++;
        Debug.Log($"Coin Collected! Score: {score}/{totalCoins}");
        if (score >= totalCoins)
        {
            Debug.Log("YOU WIN! All coins collected.");
        }
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.R))
        {
            Debug.Log("Restarting game...");
            SceneManager.LoadScene(SceneManager.GetActiveScene().name);
        }
    }
}