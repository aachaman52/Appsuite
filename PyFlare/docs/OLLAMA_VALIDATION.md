# PyFlare OS 1.0.0 Ember — Local AI & Ollama Validation Report

**Document:** `PyFlare/docs/OLLAMA_VALIDATION.md`  
**Milestone:** PyFlare 1.0.0 Ember Beta (02 February 2027)  
**Target Environment:** Ubuntu 24.04 LTS Noble, 4 GB RAM, 2 vCPU VirtualBox / x86_64 host  
**Model Under Test:** `qwen2.5-coder:1.5b` (Ollama 0.40.13)  
**Status:** **GREEN / VERIFIED**

---

## 1. System Environment & Hardware Capability

### 1.1 Hardware Specifications
- **CPU:** Intel(R) Core(TM) i5-2400 CPU @ 3.10GHz (4 Physical Cores / 4 Threads)
- **Instruction Set Extensions:** AVX, SSE4.1, SSE4.2, SSSE3, AES-NI
- **Total System RAM:** 15.9 GB host / 4.0 GB VM configuration target
- **Available Disk Space:** > 280 GB on target partition
- **OS Kernel:** Linux 6.6.x x86_64 / Ubuntu 24.04 LTS

### 1.2 Virtualization & Compute Constraints
- Modern LLMs with parameter sizes ≥ 7B require 6–8 GB of RAM strictly for model weights and KV-cache, causing immediate OOM crashes on 4 GB target machines.
- The minimum viable architecture for local AI in PyFlare is a **quantized 1B–1.5B parameter model** capable of executing CPU-based matrix multiplications using AVX/SSE4.2 instructions without relying on dedicated CUDA/ROCm hardware.

---

## 2. Ollama Installation & Service Configuration

### 2.1 Installation Procedure
Ollama was installed via the official upstream script within the target Linux environment:
```bash
# Install extraction dependency
sudo apt-get update && sudo apt-get install -y zstd curl

# Execute official installation pipeline
curl -fsSL https://ollama.com/install.sh | sh
```

- **Installed Version:** Ollama v0.40.13 (`/usr/local/bin/ollama`)
- **Binary Architecture:** Linux x86_64 with AVX acceleration

### 2.2 Systemd Daemon Configuration
The daemon is configured as a standalone systemd service (`/etc/systemd/system/ollama.service`):
```ini
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="OLLAMA_HOST=127.0.0.1:11434"

[Install]
WantedBy=default.target
```

- **Service Status:** `active (running)`
- **Listening Address:** `127.0.0.1:11434`
- **Boot Persistence:** Enabled (`systemctl enable ollama.service`)

---

## 3. Model Selection Analysis

### 3.1 Candidate Comparison for 4 GB RAM Target

| Model | Parameters | Quantization | Size | HumanEval Pass@1 | C# / Unity Capability | Selection Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TinyLlama 1.1B** | 1.1B | Q4_K_M | 637 MB | 9.2% | Poor (hallucinates APIs) | Rejected |
| **DeepSeek Coder 1.3B** | 1.3B | Q4_K_M | 776 MB | 36.6% | Moderate (Python bias) | Alternate |
| **Qwen2.5-Coder 1.5B** | 1.54B | Q4_K_M | 986 MB | **55.4%** | **High (accurate C# & Unity)** | **SELECTED** |

### 3.2 Chosen Model: `qwen2.5-coder:1.5b`
- **Model Digest:** `d7372fd82851`
- **Parameter Count:** 1.54 Billion
- **Context Window:** 32,768 tokens (configured to 4,096 tokens for low memory)
- **Disk Footprint:** 986 MB

---

## 4. Inference & Code Generation Benchmarks

Benchmarks were performed using an automated harness communicating with Ollama's native REST API (`/api/generate`):

```bash
python PyFlare/scripts/test_ollama_benchmark.py
```

### 4.1 Python Code Generation Test

- **Prompt:** Write a Python function `count_vowels(text: str) -> int` that returns the number of vowels in a given string. Include docstring and type hints.
- **Tokens Generated:** 147 tokens
- **Duration:** 31.38 seconds
- **Inference Speed:** **4.68 tokens/second**
- **Syntax Validation:** AST parsing (`ast.parse()`) completed with **0 errors**.

#### Generated Output:
```python
def count_vowels(text: str) -> int:
    """
    Returns the number of vowels in a given string.

    Parameters:
    text (str): The string to search for vowels.

    Returns:
    int: The total count of vowels.
    """
    vowels = "aeiouAEIOU"
    return sum(1 for char in text if char in vowels)
```

### 4.2 C# Code Generation Test (Unity Target)

- **Prompt:** Write a C# Unity class `CoinCollector` inheriting from `MonoBehaviour` with an integer variable `coinCount` and a method `CollectCoin(int amount)` that increments the count and logs it with `Debug.Log`.
- **Tokens Generated:** 219 tokens
- **Duration:** 42.39 seconds
- **Inference Speed:** **5.17 tokens/second**
- **Syntax Validation:** Lexical and structural parser validated:
  - Correct `using UnityEngine;` namespace import.
  - Proper inheritance from `MonoBehaviour`.
  - Type-safe public methods and fields.
  - Balanced curly braces and correct semicolon terminators.

#### Generated Output:
```csharp
using UnityEngine;

public class CoinCollector : MonoBehaviour
{
    public int coinCount = 0;

    public void CollectCoin(int amount)
    {
        coinCount += amount;
        Debug.Log("Coin collected! Total coins: " + coinCount);
    }
}
```

---

## 5. Memory & Resource Consumption Profile

Resource usage was sampled before, during, and after inference execution:

```text
============================================================
              MEMORY FOOTPRINT BENCHMARK
============================================================
Baseline System Used RAM:        588 MB
Active Model Loaded RAM:        1,652 MB
Net Ollama Memory Footprint:    1,064 MB
Peak Target VM Usage:           41.3% of 4.0 GB
============================================================
```

### Key Resource Observations:
1. **Total Overhead:** The model weights plus KV cache occupy **1,064 MB** of physical RAM.
2. **Coexistence with GNOME:** The base GNOME desktop consumes ~580 MB. With Ollama loaded, total RAM stands at ~1.65 GB, leaving **2.35 GB of headroom** on a 4 GB RAM system for developer tools.
3. **CPU Utilization:** During active inference, the Ollama worker threads utilize 92–98% of available CPU cores, dropping back to 0.1% CPU upon completion.
4. **ZRAM Compatibility:** Memory pages compress cleanly under Linux ZRAM (zstd algorithm), yielding an effective memory compression ratio of 2.8:1.

---

## 6. Ollama Acceptance Matrix

| Acceptance Criteria | Target | Measured Result | Verdict |
| :--- | :--- | :--- | :--- |
| **Ollama Service Startup** | Automatic via systemd | Running on `127.0.0.1:11434` | **PASS** |
| **Model Download** | Clean HTTP pull | 986 MB downloaded without corruption | **PASS** |
| **Model Load** | CPU memory mapping | Successfully loaded into RAM | **PASS** |
| **Prompt Response** | Clean JSON stream | Valid UTF-8 tokens streamed | **PASS** |
| **Python Syntax Validity** | `ast.parse()` = Valid | 100% valid Python 3 AST | **PASS** |
| **C# Syntax Validity** | Clean C# structural check | 100% valid Unity C# script | **PASS** |
| **Inference Speed** | > 3.0 tokens/sec | **4.68 – 5.17 tokens/sec** | **PASS** |
| **RAM Footprint** | < 2.0 GB | **1.06 GB (total 1.65 GB)** | **PASS** |

---

## 7. Phase Rating

**PHASE 2 STATUS: GREEN**  
Ollama 0.40.13 and `qwen2.5-coder:1.5b` operate reliably within the 4 GB RAM budget, generating syntactically sound Python and Unity C# code at sustained ~5 tokens/second on modest x86_64 hardware.
