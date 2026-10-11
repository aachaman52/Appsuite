# PyFlare Control Plane

This package is an executable foundation of the PyFlare master architecture. It is a
dependency-light modular core, not a claim that the complete PyFlare platform exists.

## Implemented in this foundation

- Immutable typed contracts for tasks, capabilities, providers and live hardware state
- Strict TaskSpec v1 decoding that rejects unknown or unsafe combinations
- Separate capability and provider registries
- Deterministic hard filtering and deterministic weighted route scoring
- Ordered fallback routes with machine-readable rejection reasons
- Live resource admission, priority and safe background preemption decisions
- Task-scoped path and capability authorization
- Durable SQLite task journal with optimistic revisions and idempotency records
- Deterministic workflow state transitions and acyclic step plans
- Structured validation verdicts and bounded retry/escalation decisions
- Conservative Linux hardware snapshots
- Append-only JSONL audit records with recursive secret redaction
- Transport-neutral Unity command contracts and editor-state gates
- Authenticated, loopback-only Python Unity bridge client with bounded responses
- Experimental Unity Editor package implementing editor.state.inspect and an undoable,
  unsaved game_object.create operation
- JSON Schemas for TaskSpec and Unity commands
- Unit tests, Unity-package security contract tests and dedicated GitHub Actions validation

## Deliberately not claimed as implemented

- Natural-language TaskSpec generation
- A full workflow executor that joins routing, authorization, scheduling and workers
- Unity package compilation or runtime validation inside a real Unity editor
- The broader Unity operation catalog (components, prefabs, tests, builds and imports)
- Project memory and knowledge graph integration
- Model runtime adapters
- Blender worker
- Asset registry
- Remote workers
- OS service packaging

Those are later vertical slices. Keeping this boundary explicit prevents protocol
scaffolding from being mistaken for a functional autonomous system.

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
- Mutating Unity bridge operations must be reversible in the experimental foundation.
- Skipped or inconclusive mandatory validation never counts as success.
- Retry and reroute budgets terminate in human review rather than infinite loops.
