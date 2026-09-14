# PyFlare Architecture Implementation Status

Updated: 2026-09-14 UTC

Status values are EXISTING FOUNDATION, VERIFIED FOUNDATION, PLANNED, EXPERIMENTAL and
RESEARCH. A component is not marked verified merely because a directory or placeholder
exists.

| Subsystem | Status | Current evidence |
| --- | --- | --- |
| Ubuntu/GNOME image scaffolding | EXISTING FOUNDATION | Pre-existing build, filesystem, branding, installer and validation scripts; not rebuilt in this control-plane pass |
| Desktop applications | EXPERIMENTAL | Most application entry points remain prototypes or stubs |
| TaskSpec contract | VERIFIED FOUNDATION | Typed Python contract, strict decoder, JSON Schema and unit tests |
| Capability registry | VERIFIED FOUNDATION | Duplicate-safe in-memory registry |
| Provider registry | VERIFIED FOUNDATION | Deterministic ordered registry |
| Deterministic router | VERIFIED FOUNDATION | Hard filters, explainable scoring and fallback order covered by tests |
| Hardware profiling | EXPERIMENTAL | Conservative Linux snapshot; GPU, thermal and application discovery remain incomplete |
| Resource scheduler | VERIFIED FOUNDATION | Admission and safe preemption decisions tested; no process controller yet |
| Permission model | VERIFIED FOUNDATION | Task, path and capability scopes covered by tests |
| Audit model | VERIFIED FOUNDATION | Append-only JSONL sink and recursive secret redaction |
| Workflow model | VERIFIED FOUNDATION | Explicit state transitions, acyclic plans and ready-step calculation |
| Task journal | VERIFIED FOUNDATION | SQLite WAL journal, optimistic revisions, event history and idempotency records tested |
| Validation policy | VERIFIED FOUNDATION | Mandatory validators must pass; skipped and inconclusive results are not success |
| Retry policy | VERIFIED FOUNDATION | Bounded retries, reroutes and human escalation decisions tested |
| Unity protocol | VERIFIED FOUNDATION | Commands, responses and editor-state gates |
| Python Unity client | VERIFIED FOUNDATION | Authenticated loopback transport, response bounds and protocol checks tested against a simulated HTTP bridge |
| Unity Editor bridge | EXPERIMENTAL | UPM Editor package and source-level security contract tests exist; no real Unity compile or editor runtime test yet |
| C# pipeline | PLANNED | Roslyn, Unity compilation diagnostics and assembly-aware editing are not connected |
| Context Manager | PLANNED | No version-aware project memory service exists yet |
| Knowledge graph | EXPERIMENTAL | Previously reported repository work still needs code and test verification |
| Browser agent | EXPERIMENTAL | Previously reported repository work still needs capability and security verification |
| Blender worker | PLANNED | No structured bpy worker has been verified |
| Asset registry | PLANNED | No immutable versioned object store has been verified |
| Distributed studio compute | RESEARCH | Must wait for reliable local task execution and authenticated worker identity |

## Current validated boundary

The repository now has independently tested primitives for accepting a strict TaskSpec,
routing it deterministically, checking a task-scoped grant, deciding resource admission,
recording lifecycle state and communicating with a narrowly scoped Unity bridge client.
These primitives are not yet joined by a production workflow executor.

The Unity package implements only:

1. Authenticated health checks.
2. Editor state inspection.
3. Undoable GameObject creation in an already-saved scene.
4. Main-thread dispatch, bounded queueing and durable Library-scoped idempotency.

The package intentionally leaves the scene dirty and rejects automatic scene saving.

## Next acceptance milestone

A real end-to-end vertical slice must:

1. Install and compile the UPM package in the exact supported Unity 6 editor matrix.
2. Create a validated TaskSpec from a controlled input fixture.
3. Select a route deterministically.
4. Authorize a scoped task workspace and Unity capability.
5. Admit the work using a live hardware snapshot.
6. Send an idempotent command through the real Unity Editor process.
7. Observe compilation and editor state.
8. Validate the scene result and Unity Console.
9. return a proposed diff and evidence without changing the main branch.
10. Prove timeout, token rejection, stale scene hash, duplicate request and editor-reload
    behavior.

Until that passes, PyFlare should not be described as autonomously controlling Unity.
