# PyFlare Architecture Implementation Status

Updated: 2026-09-14

Status values are VERIFIED FOUNDATION, PLANNED, EXPERIMENTAL and RESEARCH. A component is not marked verified merely because a directory or placeholder exists.

| Subsystem | Status | Current evidence |
| --- | --- | --- |
| Ubuntu/GNOME image scaffolding | VERIFIED FOUNDATION | Existing build, filesystem, branding, installer and validation scripts |
| Desktop applications | EXPERIMENTAL | Most application entry points remain stubs |
| TaskSpec contract | VERIFIED FOUNDATION | Typed Python contract and JSON Schema |
| Capability registry | VERIFIED FOUNDATION | Duplicate-safe in-memory registry |
| Provider registry | VERIFIED FOUNDATION | Deterministic ordered registry |
| Deterministic router | VERIFIED FOUNDATION | Hard filters, scoring explanations and fallback order |
| Hardware profiling | EXPERIMENTAL | Conservative Linux snapshot; GPU and thermal discovery remain incomplete |
| Resource scheduler | VERIFIED FOUNDATION | Admission and preemption policy; no process controller yet |
| Permission model | VERIFIED FOUNDATION | Task, path and capability scopes |
| Audit model | VERIFIED FOUNDATION | Append-only JSONL sink and secret redaction |
| Unity protocol | VERIFIED FOUNDATION | Commands, responses and state gates |
| Unity Editor bridge | PLANNED | No Editor package or IPC service yet |
| C# pipeline | PLANNED | Roslyn and Unity compilation integration not present |
| Context Manager | PLANNED | Existing documents do not prove a version-aware memory service |
| Knowledge graph | EXPERIMENTAL | Previously reported, but needs code and test verification |
| Browser agent | EXPERIMENTAL | Previously reported, but needs capability and security verification |
| Blender worker | PLANNED | No structured bpy worker verified |
| Asset registry | PLANNED | No immutable versioned object store verified |
| Distributed studio compute | RESEARCH | Must wait for reliable local execution |

## Next acceptance milestone

A real vertical slice must perform:

1. Accept a validated TaskSpec.
2. Select a route deterministically.
3. authorize a scoped task workspace.
4. Send an idempotent structured command to a Unity Editor package.
5. Observe Unity compilation and editor state.
6. Run validation.
7. Return a proposed diff and evidence without changing the main project branch.

Until that passes end-to-end tests, PyFlare should not be described as autonomously controlling Unity.
