# Deterministic Router Architecture V1

## Overview

PyFlare’s **Deterministic Router V1** is the central routing and dispatch layer responsible for matching user tasks to optimal local workers, MCP tools, and external cloud providers.

The core principle of PyFlare’s routing engine is **100% deterministic decision-making**:
While AI models may analyze prompts or synthesize outputs, **an AI model never makes the final routing decision**. All candidate filtering, cost constraints, privacy boundaries, hardware safety gates, and scoring math execute as standard Python code.

---

## Architectural Flow

```text
User Request / Prompt
         ↓
      TaskSpec (TaskType, Capabilities, Constraints, Privacy)
         ↓
  Capability Requirements
         ↓
Provider Registry + Hardware Profile (RAM, VRAM, CPU, Binaries)
         ↓
Deterministic Filter (Rejects Violations & Missing Prerequisites)
         ↓
Deterministic Scoring Router (Bayesian History, Latency, Cost, Quality)
         ↓
   RouteDecision
    ├── Primary Selected Route (Highest score with stable tie-breaker)
    ├── Ordered Fallback Routes (Strict fallback chain)
    └── Diagnostic Rationale (Explain every acceptance, rejection, and selection)
         ↓
Router Executor (Loop prevention, transient retry, persistent failure fallback)
         ↓
   RouteOutcome → Historical Performance Storage (Bayesian Smoothing)
```

---

## Task Specification (`TaskSpec`)

Every task submitted to PyFlare is converted into a validated Pydantic `TaskSpec`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `task_id` | `str` | Unique identifier (e.g. `task_5c750ece`) |
| `prompt` | `str` | Original user request |
| `task_type` | `TaskType` | Categorized task type (e.g. `code_generation`, `3d_generation`, `godot_automation`) |
| `required_capabilities` | `List[str]` | Mandatory capabilities needed by the task |
| `optional_capabilities` | `List[str]` | Nice-to-have capabilities |
| `privacy_level` | `PrivacyLevel` | `public`, `internal`, `confidential` |
| `max_cost_usd` | `Optional[float]` | Strict budget ceiling |
| `preferred_latency_seconds` | `Optional[float]` | Latency expectation threshold |
| `min_quality_score` | `float` | Quality score threshold (0.0 to 1.0) |
| `allow_cloud` | `bool` | Whether external cloud APIs are allowed |
| `require_local` | `bool` | Whether execution must remain strictly local |
| `required_tools` | `List[str]` | Required host binaries (e.g. `blender`, `godot`) |
| `estimated_ram_mb` | `float` | Estimated host memory needed |
| `estimated_vram_mb` | `float` | Estimated host GPU VRAM needed |

---

## Deterministic Scoring Formula

Candidates that pass all hard filters are scored using a normalized weighted formula:

$$\text{Score} = \sum_{i} w_i \times S_i$$

### Weights ($w_i$)
* $w_{\text{capability}} = 0.20$ — Capability match & required feature coverage
* $w_{\text{relevance}} = 0.15$ — Direct task type match vs. generalist model
* $w_{\text{history}} = 0.15$ — Bayesian-smoothed historical success rate
* $w_{\text{quality}} = 0.15$ — Candidate baseline quality score
* $w_{\text{latency}} = 0.10$ — Normalized expected latency ($\frac{1}{1 + \text{latency}/5}$)
* $w_{\text{cost}} = 0.10$ — Normalized cost ($\frac{1}{1 + \text{cost} \times 50}$)
* $w_{\text{hardware}} = 0.10$ — Hardware tier suitability bonus/penalty
* $w_{\text{privacy}} = 0.05$ — Local/Confidential privacy compliance bonus

### Stable Tie-Breaking
When two candidates achieve identical floating-point scores, rank is stably determined by:
$$\text{Sort Key} = (-\text{Score}, \text{candidate\_id})$$
This guarantees reproducible, deterministic route ordering across platforms.

---

## 3D Routing Policy

The router implements an explicit deterministic 3D dispatch policy:

```text
3D Request (task_type=3d_generation)
    ↓
Meshy Cloud 3D available and allowed?
    ├── Yes: Select Meshy (Score ~0.79)
    └── No: Continue
            ↓
Local Neural 3D model installed and sufficient RAM/VRAM?
    ├── Yes: Select Local 3D model
    └── No: Continue
            ↓
Blender installed in PATH?
    ├── Yes: Select Blender Automation Worker
    └── No: Return explicit 3D Policy Diagnostic
```

When no 3D route is possible, the router returns actionable setup diagnostics rather than a generic failure.
