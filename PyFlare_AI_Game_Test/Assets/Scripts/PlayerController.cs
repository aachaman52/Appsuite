using UnityEngine;

[RequireComponent(typeof(CharacterController))]
public class PlayerController : MonoBehaviour
{
    public float speed = 7.0f;
    public float gravity = 9.81f;
    private CharacterController characterController;
    private Vector3 velocity;

    void Start()
    {
        characterController = GetComponent<CharacterController>();
    }

    void Update()
    {
        if (characterController == null) return;

        float horizontalInput = Input.GetAxis("Horizontal");
        float verticalInput = Input.GetAxis("Vertical");

        Vector3 moveDirection = new Vector3(horizontalInput, 0.0f, verticalInput).normalized;
        characterController.Move(moveDirection * speed * Time.deltaTime);

        // Apply basic gravity
        if (characterController.isGrounded && velocity.y < 0)
        {
            velocity.y = -2f;
        }
        velocity.y -= gravity * Time.deltaTime;
        characterController.Move(velocity * Time.deltaTime);
    }
}