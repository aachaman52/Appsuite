import json
import time
import urllib.request
import re
from pathlib import Path

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:1.5b"

PROJECT_DIR = Path("/mnt/c/Users/Aachman_the_great/Desktop/Appsuite-1/PyFlare_AI_Game_Test")
SCRIPTS_DIR = PROJECT_DIR / "Assets" / "Scripts"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

(PROJECT_DIR / "ProjectSettings").mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / "ProjectSettings" / "ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.69f1\n", encoding="utf-8")

# Package manifest
pkg_manifest = {
    "dependencies": {
        "com.unity.modules.core": "1.0.0",
        "com.unity.modules.physics": "1.0.0",
        "com.unity.modules.ui": "1.0.0"
    }
}
(PROJECT_DIR / "Packages").mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / "Packages" / "manifest.json").write_text(json.dumps(pkg_manifest, indent=2), encoding="utf-8")

def query_ollama(prompt: str) -> dict:
    req_data = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 700
        }
    }
    payload = json.dumps(req_data).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0
    res["wall_clock_seconds"] = elapsed
    return res

def extract_code(text: str) -> str:
    matches = re.findall(r"```(?:csharp|cs)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    return text.strip()

tasks = [
    {
        "filename": "PlayerController.cs",
        "prompt": "Write a complete Unity C# script named `PlayerController` inheriting from MonoBehaviour. It should move the player horizontally and vertically using CharacterController or Rigidbody based on Input.GetAxis('Horizontal') and Input.GetAxis('Vertical'), with public float speed = 7.0f, and clamp position or move smoothly. Return only the C# code."
    },
    {
        "filename": "CameraController.cs",
        "prompt": "Write a complete Unity C# script named `CameraController` inheriting from MonoBehaviour. It should smoothly follow a target Transform (the player) with an offset Vector3(0, 5, -8). In LateUpdate, update transform.position smoothly and lookAt target. Return only the C# code."
    },
    {
        "filename": "Coin.cs",
        "prompt": "Write a complete Unity C# script named `Coin` inheriting from MonoBehaviour. It should rotate continuously around the Y axis in Update at rotationSpeed float. When another collider enters its trigger (OnTriggerEnter), check if it has the tag 'Player' or PlayerController component, notify GameManager.Instance.AddCoin(), and Destroy(gameObject). Return only the C# code."
    },
    {
        "filename": "GameManager.cs",
        "prompt": "Write a complete Unity C# script named `GameManager` inheriting from MonoBehaviour. Implement a public static GameManager Instance. Maintain int score and public int totalCoins = 5. Implement public void AddCoin() that increments score, logs 'Coin Collected!', and when score >= totalCoins, logs 'YOU WIN!'. In Update(), if Input.GetKeyDown(KeyCode.R), restart the current scene using UnityEngine.SceneManagement.SceneManager.LoadScene. Return only the C# code."
    }
]

print("=== Generating Mini 3D Coin Collector Game Scripts via Ollama ===")

results = []
for t in tasks:
    fname = t["filename"]
    print(f"\nPrompting for {fname}...")
    res = query_ollama(t["prompt"])
    code = extract_code(res["response"])
    
    # Save script
    target_path = SCRIPTS_DIR / fname
    target_path.write_text(code, encoding="utf-8")
    
    eval_count = res.get("eval_count", 0)
    eval_duration = res.get("eval_duration", 1) / 1e9
    tps = eval_count / eval_duration if eval_duration > 0 else 0
    
    print(f"Generated {fname} ({len(code)} bytes):")
    print(f"  Tokens: {eval_count}, Duration: {eval_duration:.2f}s, Speed: {tps:.2f} tokens/sec")
    
    results.append({
        "file": fname,
        "tokens": eval_count,
        "duration_sec": round(eval_duration, 2),
        "tps": round(tps, 2),
        "code_snippet": code[:120] + "..."
    })

print("\n--- Generation Summary ---")
print(json.dumps(results, indent=2))
