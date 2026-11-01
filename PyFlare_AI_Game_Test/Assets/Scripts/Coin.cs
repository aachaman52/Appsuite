using UnityEngine;

public class Coin : MonoBehaviour
{
    public float rotationSpeed = 5.0f;

    void Update()
    {
        // Rotate continuously around the Y axis
        transform.Rotate(Vector3.up, rotationSpeed * Time.deltaTime);
    }

    void OnTriggerEnter(Collider other)
    {
        // Check if the collider has the tag 'Player' or PlayerController component
        if (other.CompareTag("Player") || other.GetComponent<PlayerController>() != null)
        {
            // Notify GameManager.Instance.AddCoin()
            GameManager.Instance.AddCoin();
            // Destroy the coin
            Destroy(gameObject);
        }
    }
}