# PyFlare Capability Registry

## Overview

The `CapabilityRegistry` manages candidate execution nodes (cloud LLMs, local neural models, specialized workers, and deterministic rule engines). Each candidate declares its supported task types, resource requirements, quality benchmarks, and prerequisite credentials or binaries.

---

## Default Registered Candidates

| Candidate ID | Type | Mode | Privacy | Cost / Task | Latency | Key / Executable Prerequisite | Supported Tasks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `openai-cloud` | `cloud_llm` | Cloud | Public | $0.0150 | 1.8s | `OPENAI_API_KEY` | `code_generation`, `code_analysis`, `research`, `general`, `validation` |
| `gemini-cloud` | `cloud_llm` | Cloud | Public | $0.0080 | 1.5s | `GEMINI_API_KEY` | `code_generation`, `code_analysis`, `research`, `general`, `image_generation` |
| `claude-cloud` | `cloud_llm` | Cloud | Public | $0.0150 | 2.0s | `ANTHROPIC_API_KEY` | `code_generation`, `code_analysis`, `research`, `general`, `validation` |
| `local-llm` | `local_llm` | Local | Confidential | $0.0000 | 3.5s | Requires 4096MB RAM | `code_generation`, `code_analysis`, `general`, `validation` |
| `local-fallback-rules` | `local_rules` | Local | Confidential | $0.0000 | 0.05s | Zero prerequisites | `code_generation`, `code_analysis`, `general`, `asset_processing`, `validation` |
| `blender-worker` | `local_worker` | Local | Confidential | $0.0000 | 5.0s | `blender` in PATH, 2048MB RAM | `3d_generation`, `blender_automation`, `asset_processing` |
| `godot-worker` | `local_worker` | Local | Confidential | $0.0000 | 3.0s | `godot` in PATH, 1536MB RAM | `godot_automation`, `asset_processing`, `validation` |
| `internet-worker` | `network_worker` | Hybrid | Public | $0.0000 | 2.5s | Network access | `research`, `asset_processing` |
| `validation-worker` | `local_worker` | Local | Confidential | $0.0000 | 0.8s | 256MB RAM | `validation`, `code_analysis` |
| `code-worker` | `hybrid_worker` | Local | Internal | $0.0000 | 1.2s | 512MB RAM | `code_generation`, `code_analysis` |
| `deploy-worker` | `deployment_worker`| Local | Internal | $0.0000 | 2.0s | 512MB RAM | `deployment` |
| `meshy-3d` | `cloud_3d` | Cloud | Public | $0.0500 | 12.0s | `MESHY_API_KEY` | `3d_generation` |
| `local-3d-model` | `local_3d` | Local | Confidential | $0.0000 | 15.0s | 8192MB RAM, 4096MB VRAM | `3d_generation` |

---

## Dynamic Availability Evaluation

When listing or querying candidates, `CapabilityRegistry` evaluates prerequisites:
1. **API Key Checks**: Inspects `os.environ` for required environment variables. If absent, marks `is_available = False` with `unavailability_reason = "Missing environment variable: <KEY>"`.
2. **Binary Tool Checks**: Hardware manager checks presence in `PATH`. If missing, the worker candidate is rejected during router filtering with an explicit diagnostic.
3. **Hardware Constraints**: RAM and VRAM availability are verified against live system metrics.
