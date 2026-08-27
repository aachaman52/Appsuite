# Deterministic Router V1 Implementation Report

**PyFlare Autonomous Platform**  
**Branch:** `refactor/pyflare-cleanup`  
**Milestone:** Phase 1 — Deterministic Routing Layer  

---

## 1. Executive Summary

We have implemented **Deterministic Router V1** for PyFlare. The router replaces ad-hoc LLM or worker selection with a 100% deterministic, hardware-aware, cost-bounded, and privacy-confined dispatch layer. 

No AI model makes the final routing decision. All filtering, constraint validation, scoring, and fallback chain evaluations are executed strictly in deterministic Python code.

---

## 2. Files Created and Modified

### Newly Created Files
* `src/pyflare/router/models.py` — Validated Pydantic models for `TaskSpec`, `CapabilityRequirement`, `ProviderCapability`, `HardwareProfile`, `RouteCandidate`, `RouteDecision`, `ExecutionConstraint`, and `RouteOutcome`.
* `src/pyflare/router/capability_registry.py` — Central capability registry connecting cloud LLMs, local models, MCP tools, and worker engines.
* `src/pyflare/router/history.py` — Persistent SQLite performance store (`router_history`) with Bayesian smoothing (m-estimate) to prevent outlier runs from skewing routing scores.
* `src/pyflare/router/scoring.py` — Deterministic candidate filtering and normalized multi-factor composite scoring engine.
* `src/pyflare/router/router.py` — Central `DeterministicRouter` with stable tie-breaking and domain-specific 3D dispatch logic.
* `src/pyflare/router/executor.py` — Resilient `RouterExecutor` orchestrating primary routes, retry limits, non-retryable error detection (401/403/policy), and loop prevention.
* `src/pyflare/router/__init__.py` — Clean public exports for the router package.
* `tests/unit/test_router.py` — 17 unit tests verifying deterministic output, stable tie-breaking, weak hardware, missing GPU/binaries/keys, privacy confinement, 3D routing policy, and Bayesian smoothing.
* `tests/unit/test_router_api.py` — 5 unit tests verifying `/router/plan`, `/router/capabilities`, `/router/hardware`, and authenticated `/router/execute` and `/router/history` endpoints.
* `docs/ROUTER_ARCHITECTURE.md` — Complete router architecture specification.
* `docs/CAPABILITY_REGISTRY.md` — Candidate registration schema and default provider catalog.
* `docs/HARDWARE_ROUTING.md` — Host hardware telemetry and resource routing guide.

### Modified Files
* `src/pyflare/core/hardware_manager.py` — Extended with `get_hardware_profile() -> HardwareProfile`, normalized hardware tiers (`weak`, `mid`, `high`), non-blocking binary detection, and GPU VRAM fallback.
* `src/pyflare/api/routes.py` — Added endpoints: `POST /router/plan`, `POST /router/execute`, `GET /router/capabilities`, `GET /router/hardware`, and `GET /router/history`.
* `src/pyflare/cli.py` — Added subcommands `pyflare route`, `pyflare capabilities`, `pyflare hardware`, and `pyflare validate-os`.
* `src/pyflare/plugins/plugin_manager.py` — Added `enabled`, `load()`, and `list()` methods for clean lifecycle management.
* `src/pyflare/core/health.py` — Added `run_doctor_checks` preflight diagnostic function.
* `README.md` — Updated with an honest Component Status Matrix, architecture diagram, and CLI routing examples.

---

## 3. Mathematical Routing Formula

For every candidate satisfying all hard filters (privacy, cloud restrictions, hardware RAM/VRAM, required tools, and task type), the composite score $S \in [0.0, 1.0]$ is computed as:

$$S = \sum_{k} w_k \cdot f_k(\text{Candidate}, \text{Task}, \text{Hardware}, \text{History})$$

### Default Weights ($w_k$)
* **Capability Match ($w = 0.20$):** Mean capability coverage for required task capabilities.
* **Task Relevance ($w = 0.15$):** $1.0$ for exact domain match, $0.70$ for generalist model, $0.50$ otherwise.
* **Historical Success ($w = 0.15$):** Bayesian smoothed rate $\hat{p} = \frac{\text{successes} + 5 \times 0.85}{N + 5}$.
* **Quality Score ($w = 0.15$):** Baseline verified quality rating ($0.0$ to $1.0$).
* **Latency Score ($w = 0.10$):** Normalized latency score $f(L) = \frac{1}{1 + L/5.0}$.
* **Cost Score ($w = 0.10$):** Normalized cost score $f(C) = \frac{1}{1 + C \times 50.0}$.
* **Hardware Suitability ($w = 0.10$):** Host tier compatibility score ($1.0$ high, $0.85$ mid, $0.65$ weak; $0.95$ for cloud).
* **Privacy Compliance ($w = 0.05$):** Bonus for local/confidential processing.

### Stable Tie-Breaking
When candidates achieve identical scores, deterministic ordering is enforced by:
$$\text{Rank Key} = (-\text{Score}, \text{candidate\_id})$$

---

## 4. Hardware Detection & Host Safety

* **Normalized Tiers:**
  * `high`: $\ge 16\text{ GB RAM}$, $\ge 6\text{ GB VRAM}$, $\ge 8\text{ logical CPU cores}$.
  * `mid`: $\ge 8\text{ GB RAM}$, $(\ge 2\text{ GB VRAM} \text{ or } \ge 4\text{ logical CPU cores})$.
  * `weak`: $< 8\text{ GB RAM}$ or $< 500\text{ MB available RAM}$.
* **Host Protection:**
  * Candidates requiring more RAM than currently available (`hardware.ram_available_mb`) are rejected before execution.
  * Blender and Godot workers run gracefully on CPU without discrete NVIDIA GPU crashes.
  * System RAM monitor throttles heavy worker dispatch if memory pressure exceeds 85%.

---

## 5. Verification Results

### Test Suite Execution
* **Unit Tests:** 144 passed, 9 xfailed
* **Integration Tests:** 28 passed, 1 xfailed
* **Total Tests:** **172 passed, 10 xfailed, 0 unhandled failures**

### Linter & Type Checks
* **Ruff:** `All checks passed!` (0 errors)
* **Compileall:** `python -m compileall src` passed with exit code 0.
* **Mypy:** `src/pyflare/router/` contains **0 typing errors**. Existing typing debt in legacy core components is documented and preserved.

### CLI Verification
* `pyflare doctor` — System diagnostics pass cleanly.
* `pyflare hardware` — Detects 8 logical cores, 7.8GB RAM, and binary status.
* `pyflare capabilities` — Lists all 13 registered candidate providers with dynamic availability.
* `pyflare route "Generate a 3D procedural tree"` — Generates deterministic 3D diagnostic plan.
* `pyflare route "Write a Python parser for math equations"` — Selects `code-worker` with score `0.9051` and `local-fallback-rules` fallback.
* `pyflare validate-os` — Runs all 14 PyFlare OS static validators in 0.17s without heavy ISO builds.

---

## 6. Remaining Limitations & Next Steps

1. **Live 3D Cloud API Mocking:** External cloud 3D providers (Meshy) currently operate via capability adapters and require a valid `MESHY_API_KEY` for live execution.
2. **Context Window Manager:** Next milestone should enhance conversational and multi-turn context compaction algorithms.
3. **Repository Split for PyFlare OS:** PyFlare OS source assets remain safely archived in `archive/pyflareos/` with automated static validation. Repository separation is documented for future standalone migration.
