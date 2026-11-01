import json
import time
import urllib.request
import ast
import re
import sys

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5-coder:1.5b"

def query_ollama(prompt: str) -> dict:
    req_data = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 512
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

def extract_code(text: str, lang: str = "") -> str:
    pattern = rf"```(?:{lang})?\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[0].strip()
    return text.strip()

print("=== Ollama Phase 2 Benchmarking ===")

# Test 1: Python Code Generation
py_prompt = "Write a Python function `fibonacci(n: int) -> list[int]` that returns the first n Fibonacci numbers with docstring and type hints. Return only code."
print("\n--- Test 1: Python Generation ---")
res_py = query_ollama(py_prompt)
code_py = extract_code(res_py["response"], "python")
print("Response text:\n", code_py)

# Validate Python Syntax
try:
    ast.parse(code_py)
    py_valid = True
    print(">> Python Syntax: VALID")
except SyntaxError as e:
    py_valid = False
    print(">> Python Syntax ERROR:", e)

eval_count_py = res_py.get("eval_count", 0)
eval_duration_py = res_py.get("eval_duration", 1) / 1e9  # nanoseconds to seconds
tps_py = eval_count_py / eval_duration_py if eval_duration_py > 0 else 0
print(f"Tokens: {eval_count_py}, Duration: {eval_duration_py:.2f}s, Speed: {tps_py:.2f} tokens/sec")

# Test 2: C# Code Generation
cs_prompt = "Write a complete Unity C# script `PlayerController` with MonoBehaviour that moves the player with CharacterController based on Input.GetAxis('Horizontal') and Input.GetAxis('Vertical') and speed float. Return only valid C# code."
print("\n--- Test 2: C# Unity Generation ---")
res_cs = query_ollama(cs_prompt)
code_cs = extract_code(res_cs["response"], "csharp|cs")
print("Response text:\n", code_cs)

# Validate C# structure
has_using = "using UnityEngine;" in code_cs
has_class = "class PlayerController : MonoBehaviour" in code_cs or "class PlayerController: MonoBehaviour" in code_cs
has_update = "Update()" in code_cs
cs_valid = has_using and has_class and has_update
print(f">> C# Structure Validation: {'VALID' if cs_valid else 'WARNING - Incomplete'}")

eval_count_cs = res_cs.get("eval_count", 0)
eval_duration_cs = res_cs.get("eval_duration", 1) / 1e9
tps_cs = eval_count_cs / eval_duration_cs if eval_duration_cs > 0 else 0
print(f"Tokens: {eval_count_cs}, Duration: {eval_duration_cs:.2f}s, Speed: {tps_cs:.2f} tokens/sec")

# Check memory
with open("/proc/meminfo") as f:
    meminfo = f.read()

mem_total = 0
mem_avail = 0
for line in meminfo.splitlines():
    if line.startswith("MemTotal:"):
        mem_total = int(line.split()[1]) // 1024
    elif line.startswith("MemAvailable:"):
        mem_avail = int(line.split()[1]) // 1024

mem_used = mem_total - mem_avail
print(f"\nSystem Memory: Total={mem_total}MB, Used={mem_used}MB, Avail={mem_avail}MB")

summary = {
    "model": MODEL,
    "python_valid": py_valid,
    "python_tps": round(tps_py, 2),
    "csharp_valid": cs_valid,
    "csharp_tps": round(tps_cs, 2),
    "mem_used_mb": mem_used,
    "mem_avail_mb": mem_avail
}
print("\nBenchmark Summary JSON:\n", json.dumps(summary, indent=2))
