# PyFlare Control Plane

This package is the first executable foundation of the PyFlare master architecture. It is intentionally a small, dependency-light modular core, not a claim that the complete PyFlare platform exists.

## Implemented in this foundation

- Immutable typed contracts for tasks, capabilities, providers and live hardware state
- Separate capability and provider registries
- Deterministic hard filtering and deterministic weighted route scoring
- Ordered fallback routes with machine-readable rejection reasons
- Live resource admission, priority and safe background preemption decisions
- Task-scoped path and capability authorization
- Conservative Linux hardware snapshots
- Append-only JSONL audit records with recursive secret redaction
- Transport-neutral Unity command contracts
- Unity edit/play/compile/scene-version state gates
- JSON Schemas for TaskSpec and Unity commands
- Unit tests and dedicated GitHub Actions validation

## Deliberately not claimed as implemented

- Natural-language TaskSpec generation
- Executing routed plans
- Unity Editor extension or IPC transport
- Project memory and knowledge graph integration
- Model runtime adapters
- Blender worker
- Asset registry
- Remote workers
- OS service packaging

Those are later vertical slices. Keeping this boundary explicit prevents protocol scaffolding from being mistaken for a functional autonomous system.

## Run

    cd PyFlare/control_plane
    python -m pip install -e ".[dev]"
    ruff check src tests
    python -m unittest discover -s tests -v
    pyflare-control hardware

## Design rules

- Final routing authority is deterministic.
- Hard policy failures cannot be overridden by scoring.
- Deterministic tools and applications are preferred when they satisfy the task.
- Current available resources matter, not only maximum hardware specifications.
- A route does not authorize execution. Permission grants are evaluated separately.
- A route does not guarantee admission. The scheduler independently protects responsiveness.
- Unity commands require idempotency keys and explicit editor-state preconditions.
