# Last Work: PyFlare Control Plane and Unity Foundation

**Date:** 2026-09-14 UTC  
**Repository:** Aachman Studios / Appsuite  
**Working branch:** codex/pyflare-control-plane-foundation  
**Pull request:** [#1 — Build PyFlare deterministic control-plane foundation](https://github.com/aachaman52/Appsuite/pull/1)  
**Base commit:** 461796f6992cb3ca7b71c121d14ff312087d490b  
**Last audited code commit before this document:** a05dbac3ba7384a16fee2b0301045e4aa65dd4fe  
**Merge status:** Not merged. Human review is still required.

This document is the durable handoff for the implementation work completed on
2026-09-14. It records what changed, what was tested, what is only experimental and
what should happen next. It does not claim that the complete PyFlare architecture is
implemented.

## 1. Outcome

A serious executable foundation now exists for PyFlare's deterministic control plane
and its Unity-first automation direction.

The implemented code can currently:

- Represent and strictly decode versioned TaskSpec documents.
- Register capabilities and providers independently.
- Deterministically hard-filter, score and order execution routes.
- Protect live RAM, VRAM and CPU headroom through admission decisions.
- Enforce task-scoped capabilities and project-relative path permissions.
- Capture a conservative Linux hardware snapshot.
- Record redacted append-only audit events.
- Model valid task-state transitions and dependency-safe workflow plans.
- Persist tasks, events and operation idempotency in SQLite.
- Evaluate structured validation results without treating skipped work as success.
- Make bounded retry, reroute and human-escalation decisions.
- Model Unity commands and reject stale or unsafe editor states.
- Send authenticated commands to a loopback-only Unity bridge from Python.
- Host an experimental Unity Editor extension that inspects editor state and creates
  one undoable, unsaved GameObject through structured JSON.

The code does not yet convert natural language into a TaskSpec, execute an entire
workflow, manage project memory, control Blender, version assets, schedule remote
workers or build a production PyFlare OS image.

## 2. Status legend

| Label | Meaning |
| --- | --- |
| EXISTING FOUNDATION | Code or assets already present in the repository; this pass may document but did not necessarily revalidate them |
| VERIFIED FOUNDATION | Narrow implementation covered by the Python lint and unittest gate |
| EXPERIMENTAL | Concrete code exists, but an important runtime or integration test is still missing |
| PLANNED | Architecture is specified but functional code is not present |
| RESEARCH | Design requires benchmarking or feasibility work before a stable choice |

## 3. Dated commit trail

All commits below were created on 2026-09-14 UTC.

| Commit | Change |
| --- | --- |
| 6c7ec8d | Added the first dependency-light PyFlare control-plane package, contracts, deterministic router, scheduler, security, audit, hardware profiling, Unity protocol, schemas, tests and CI |
| 784f201 | Corrected initial Python lint/import findings |
| 33b7cb4 | Preserved the full PyFlare Master Architecture & Development Plan and corrected the audit implementation |
| 6fa8136 | Added strict TaskSpec decoding, workflow state, SQLite task journal, validation policy and bounded retry policy |
| 6b35608 | Added the Python Unity client and experimental authenticated Unity Editor package |
| 1c2614f | Expanded security contract tests, workflow triggers, package exports and implementation documentation |
| 559a4c6 | Corrected the remaining test-file lint formatting |
| a05dbac | Removed an invalid package export and strengthened Unity GlobalObjectId and Undo safeguards |
| This document's commit | Updated status documentation and added this root handoff file |

No commit in this work was pushed to main directly. Work remains isolated in the pull
request branch.

## 4. Architecture slice now present

The current implemented control path is:

    TaskSpec
      -> Capability and provider registries
      -> Deterministic router
      -> Task-scoped authorization
      -> Resource admission
      -> Transport-neutral Unity command
      -> Authenticated loopback client
      -> Unity bridge request queue
      -> Unity editor main-thread operation
      -> Structured response
      -> Validation and bounded retry decisions
      -> Durable task and audit records

Important boundary: these parts are implemented as composable primitives. A production
workflow service does not yet join every arrow automatically.

## 5. Subsystem walkthrough

### 5.1 Versioned contracts and strict TaskSpec decoding — VERIFIED FOUNDATION

The models module defines immutable contracts for tasks, permissions, resource budgets,
hardware snapshots, capabilities, providers and provider measurements.

The codec module converts untrusted JSON-like input into a TaskSpec. It:

- Requires schema version 1.0.
- Rejects missing required fields.
- Rejects unknown fields instead of silently ignoring them.
- Rejects invalid enum values and incorrect primitive types.
- Rejects duplicate capability, permission and application entries.
- Distinguishes booleans from integers.
- Validates RAM, VRAM, CPU and monetary budgets.
- Rejects local-only privacy combined with cloud execution.
- Produces a stable canonical dictionary for storage and hashing.

The JSON Schema remains useful at API boundaries, while the Python decoder is the
runtime authority inside this package.

### 5.2 Capability and provider registries — VERIFIED FOUNDATION

Capabilities describe what can be done and which permissions and validators are
required. Providers describe who or what can perform capabilities.

The registries are deliberately separate. Unity, Blender, a compiler, a script, a local
model and a cloud model can all be providers. Duplicate identifiers are rejected and
provider enumeration is deterministic.

### 5.3 Deterministic router — VERIFIED FOUNDATION

The router never delegates final route authority to a model. It first applies hard
filters for:

- Required capabilities.
- Provider availability and circuit state.
- Network state.
- Cloud and remote-compute policy.
- Local-only privacy.
- Monetary budget.
- Task RAM and VRAM budgets.
- Live RAM and VRAM headroom.
- Required applications.
- Minimum measured quality.
- Minimum historical success after enough samples.

Accepted candidates receive explainable score components for quality, historical
success, latency, resource fitness, availability, cost fitness, privacy fitness,
deterministic-tool preference and foreground interference. Ties are resolved by stable
provider identifier ordering. The output contains one primary route, ordered fallbacks
and all rejection reasons.

A deterministic tool can therefore beat a larger AI provider when both satisfy the
task.

### 5.4 Hardware profiler and resource scheduler — FOUNDATION / EXPERIMENTAL

The hardware profiler captures a conservative Linux snapshot without adding heavy
dependencies. Current resource availability, not just installed capacity, enters
routing.

The scheduler independently checks admission after routing. It preserves configurable
RAM, VRAM and CPU margins and can propose preemption only for lower-priority,
explicitly preemptible reservations. It returns admitted, queued or reroute-required;
it does not yet control operating-system processes.

GPU discovery, thermal telemetry, disk performance measurement and complete
application/runtime discovery require additional implementation and benchmarking.

### 5.5 Authorization and audit — VERIFIED FOUNDATION

Permission grants are bound to one task, one subject and one project root. They contain
explicit permission types, allowed paths, denied paths, capabilities and optional
expiry. Resolved paths outside the project root are rejected.

Routing does not imply authorization. Admission does not imply authorization. These
remain separate checks.

The audit sink appends JSON Lines and recursively redacts values under secret-like keys.
It records structured action metadata without intentionally storing provider tokens.

### 5.6 Workflow state and durable task journal — VERIFIED FOUNDATION

The workflow module defines explicit task states:

    draft -> authorized -> queued -> running -> validating
      -> completed -> merged

It also defines bounded retry, review, failure and cancellation branches. Invalid state
jumps are rejected. Workflow steps have unique identifiers, declared dependencies,
cycle detection and ready-step calculation.

The SQLite journal uses:

- Foreign keys.
- Write-ahead logging.
- Immediate transactions for state changes.
- Optimistic revision checks to reject stale writers.
- Append-only task events.
- Canonical stored TaskSpec and metadata JSON.
- Operation idempotency reservations and completed-response replay.

This is a local durable foundation. Multi-process load, corruption recovery, migrations,
backup, studio replication and retention policy are not yet benchmarked.

### 5.7 Validation and retry policy — VERIFIED FOUNDATION

Validators report identity, version, pass/fail/inconclusive/skipped status, findings,
evidence references and duration.

A required validator must be present and pass. Skipped and inconclusive validators do
not count as success. A passing result cannot contain error or critical findings.

Retry decisions are deterministic and budgeted. Permission or policy denial escalates
to a human rather than retrying. Resource exhaustion reschedules or reroutes.
Structured-output errors get a limited repair attempt. Repeated identical failures,
expired budgets and exhausted route changes terminate in human review rather than an
infinite loop.

### 5.8 Unity protocol and Python client — VERIFIED FOUNDATION

The transport-neutral Unity protocol requires:

- Protocol pyflare-unity/1.0.
- Request, task and project identifiers.
- Operation name and arguments.
- Explicit editor preconditions.
- A non-empty idempotency key.
- Explicit Undo and scene-save intent.

The Python client:

- Allows only plain HTTP to 127.0.0.1, localhost or ::1 with an explicit port.
- Rejects URL credentials, query strings, fragments and endpoint paths.
- Requires a token of at least 32 characters.
- Sends the token in X-PyFlare-Token, never in the URL.
- Uses finite JSON and rejects unserializable arguments.
- Applies timeouts and maximum response size.
- Distinguishes transport, security and protocol failures.
- Validates protocol, status, arrays, result shape and matching request ID.
- Does not automatically retry side-effecting commands.

Retries stay above the transport where idempotency and task budgets are visible.

### 5.9 Unity Editor package — EXPERIMENTAL

The Unity Package Manager package is located at:

    PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation

It targets Unity 6 with a manifest minimum of 6000.0. The bridge:

- Is Editor-only.
- Loads on demand unless explicitly enabled through the environment.
- Binds only to http://127.0.0.1:47831.
- Refuses to start without a token of at least 32 characters.
- Authenticates every health check and command using a timing-resistant comparison.
- Rejects non-loopback callers.
- Accepts at most 1 MiB per request.
- Limits the pending queue to 128 requests.
- Dispatches at most 8 requests per editor update.
- Times out work delayed in the editor queue.
- Keeps network work off the Unity API thread.
- Executes Unity APIs only from EditorApplication.update.
- Closes pending work during editor shutdown or assembly reload.
- Stores idempotency fingerprints and responses under the disposable Library directory.
- Rejects reuse of an idempotency key with a different request.
- Returns stable error codes without returning exception details.

Implemented operations:

| Operation | Current behavior |
| --- | --- |
| editor.state.inspect | Reports edit/play/transition mode, compilation, Asset Database refresh, active scene path and saved scene SHA-256 |
| game_object.create | Creates a named GameObject with optional world position and optional parent GlobalObjectId |

The mutating operation requires Edit Mode, idle compilation, a non-refreshing Asset
Database, matching optional scene preconditions, an active scene saved at least once
and Undo registration. It registers creation and hierarchy changes with Unity Undo,
marks the scene dirty and deliberately refuses to save the scene in bridge version 0.1.

The code uses Unity GlobalObjectId because it is a stable project-scoped editor
identifier. The implementation was corrected after checking Unity's official Unity 6
documentation: a scene must be saved at least once for a valid scene object identifier,
and object changes should be registered after creation so Undo captures them.

This package has not yet been compiled or executed inside Unity. Source-level contract
tests do not prove C# compilation, HttpListener behavior, editor lifecycle correctness
or scene mutation correctness. Those remain release blockers.

## 6. File-by-file inventory

### Repository and documentation

| Path | Status | Change |
| --- | --- | --- |
| .github/workflows/pyflare-control-plane.yml | VERIFIED FOUNDATION | Adds Ubuntu 24.04 Python install, Ruff and unittest gates; now also triggers for Unity integration changes |
| PyFlare/README.md | DOCUMENTATION | Defines PyFlare as an operating environment, links the foundation, status, Unity package and this handoff |
| PyFlare/docs/IMPLEMENTATION_STATUS.md | DOCUMENTATION | Separates existing, verified, planned, experimental and research components |
| PyFlare/docs/PYFLARE_MASTER_ARCHITECTURE_AND_DEVELOPMENT_PLAN.md | DOCUMENTATION | Preserves the complete Unity-first master architecture and phased development plan |
| Last_Work.md | DOCUMENTATION | This dated, complete implementation and continuation walkthrough |

### Python package and schemas

| Path | Status | Change |
| --- | --- | --- |
| PyFlare/control_plane/pyproject.toml | VERIFIED FOUNDATION | Defines the Python 3.12 package, CLI and development dependencies |
| PyFlare/control_plane/README.md | DOCUMENTATION | Records the executable boundary and local validation commands |
| PyFlare/control_plane/schemas/taskspec.v1.schema.json | VERIFIED FOUNDATION | Machine-readable TaskSpec v1 boundary |
| PyFlare/control_plane/schemas/unity-command.v1.schema.json | VERIFIED FOUNDATION | Machine-readable Unity command v1 boundary |
| PyFlare/control_plane/src/pyflare_control/__init__.py | VERIFIED FOUNDATION | Exposes the supported package surface |
| PyFlare/control_plane/src/pyflare_control/models.py | VERIFIED FOUNDATION | Immutable tasks, resources, permissions, providers and hardware contracts |
| PyFlare/control_plane/src/pyflare_control/codec.py | VERIFIED FOUNDATION | Strict TaskSpec decoding and canonical encoding |
| PyFlare/control_plane/src/pyflare_control/registry.py | VERIFIED FOUNDATION | Capability and provider registries |
| PyFlare/control_plane/src/pyflare_control/router.py | VERIFIED FOUNDATION | Hard gates, explainable scoring, primary and fallback routes |
| PyFlare/control_plane/src/pyflare_control/scheduler.py | VERIFIED FOUNDATION | Resource admission and safe preemption decisions |
| PyFlare/control_plane/src/pyflare_control/security.py | VERIFIED FOUNDATION | Scoped capabilities, permissions and filesystem boundaries |
| PyFlare/control_plane/src/pyflare_control/audit.py | VERIFIED FOUNDATION | Append-only structured records and recursive secret redaction |
| PyFlare/control_plane/src/pyflare_control/hardware.py | EXPERIMENTAL | Conservative Linux resource snapshot |
| PyFlare/control_plane/src/pyflare_control/control_plane.py | VERIFIED FOUNDATION | Composition of authorization, routing and admission |
| PyFlare/control_plane/src/pyflare_control/workflow.py | VERIFIED FOUNDATION | Task state machine and dependency-safe workflow plans |
| PyFlare/control_plane/src/pyflare_control/journal.py | VERIFIED FOUNDATION | Durable SQLite tasks, events, revisions and idempotency |
| PyFlare/control_plane/src/pyflare_control/validation.py | VERIFIED FOUNDATION | Structured results and mandatory-validator acceptance |
| PyFlare/control_plane/src/pyflare_control/retry.py | VERIFIED FOUNDATION | Bounded retry, reschedule, reroute and escalation policy |
| PyFlare/control_plane/src/pyflare_control/unity_protocol.py | VERIFIED FOUNDATION | Unity command, response, editor state and state gates |
| PyFlare/control_plane/src/pyflare_control/unity_client.py | VERIFIED FOUNDATION | Authenticated loopback HTTP client |
| PyFlare/control_plane/src/pyflare_control/cli.py | VERIFIED FOUNDATION | Conservative hardware diagnostic command |

### Python test suite

| Path | Coverage |
| --- | --- |
| PyFlare/control_plane/tests/test_codec.py | Strict types, unknown fields, privacy/cloud conflict and stable round trip |
| PyFlare/control_plane/tests/test_router.py | Cloud gates, offline routing, no-route evidence and deterministic-tool preference |
| PyFlare/control_plane/tests/test_scheduler.py | Headroom admission and lower-priority preemption |
| PyFlare/control_plane/tests/test_security.py | Project root, allowlist and denylist path boundaries |
| PyFlare/control_plane/tests/test_workflow_journal.py | State transitions, stale revisions, event history, idempotency and workflow cycles |
| PyFlare/control_plane/tests/test_validation_retry.py | Required validation, skipped validation, permission escalation and repeated-failure limits |
| PyFlare/control_plane/tests/test_unity_protocol.py | Idle editor acceptance and stale/busy editor rejection |
| PyFlare/control_plane/tests/test_unity_client.py | Authenticated health, command round trip, request matching, endpoint policy, token policy and response bounds |
| PyFlare/control_plane/tests/test_unity_package_contract.py | UPM manifest and security-critical C# source invariants |

### Unity package

| Path | Status | Change |
| --- | --- | --- |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/package.json | EXPERIMENTAL | Unity Package Manager identity, version and minimum editor version |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/README.md | DOCUMENTATION | Installation, protocol, operations, safety boundaries and runtime limitations |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/Editor/PyFlare.Automation.Editor.asmdef | EXPERIMENTAL | Editor-only assembly boundary |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/Editor/BridgeContracts.cs | EXPERIMENTAL | JSON command, response, state and idempotency DTOs |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/Editor/BridgeSecurity.cs | EXPERIMENTAL | Loopback verification, timing-resistant token comparison and request bounds |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/Editor/BridgeIdempotencyStore.cs | EXPERIMENTAL | Hashed Library-scoped request fingerprints and response replay |
| PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/Editor/PyFlareUnityBridge.cs | EXPERIMENTAL | On-demand authenticated listener, bounded queue, main-thread dispatcher, state inspection and reversible GameObject creation |

## 7. Validation evidence

Latest successful GitHub Actions run:

- Workflow: PyFlare Control Plane
- Run ID: 34866970165
- Runner: ubuntu-24.04
- Python: 3.12
- Install: passed
- Ruff: passed with “All checks passed”
- Tests: 31 passed in 0.557 seconds
- Result: success
- Validated code commit: a05dbac3ba7384a16fee2b0301045e4aa65dd4fe

The earlier failing runs were retained rather than hidden:

| Run ID | Result | Finding | Correction |
| --- | --- | --- | --- |
| 34866194175 | Failed at lint | Modern Ruff typing, import and mutable class-default findings | Corrected annotations, imports and ClassVar use |
| 34866551132 | Failed at lint | One new contract-test import block had an extra blank line | Corrected formatting |
| 34866711015 | Failed at tests | Package initializer exported a class name not defined by the journal | Removed the stale export |
| 34866970165 | Passed | All current Python and source-contract checks passed | Current evidence |

The earlier architecture foundation was also green in run 34863301099 before the new
vertical slice was added.

## 8. How to reproduce the verified checks

From the repository root:

    cd PyFlare/control_plane
    python -m pip install -e ".[dev]"
    ruff check src tests
    python -m unittest discover -s tests -v
    pyflare-control hardware

The hardware command intentionally does not probe the internet. Network availability
must be declared by the caller.

## 9. How to exercise the experimental Unity package

Do not treat this as production setup.

1. Open a disposable Unity 6 test project.
2. In Package Manager, choose Add package from disk.
3. Select:

       PyFlare/integrations/unity/com.aachmanstudios.pyflare.automation/package.json

4. Launch Unity with a random token of at least 32 characters supplied through the
   process environment:

       PYFLARE_UNITY_BRIDGE_TOKEN=<random-development-secret>
       PYFLARE_UNITY_BRIDGE_ENABLED=1

5. If automatic startup is disabled, choose Tools > PyFlare > Unity Bridge > Start.
6. Use only a disposable test scene that has been saved at least once.
7. Keep save_scene false. Version 0.1 rejects automatic saving.
8. Verify the Console, Hierarchy, Undo behavior, active scene hash and response.
9. Stop the bridge through Tools > PyFlare > Unity Bridge > Stop.

The token should eventually come from the OS secret service and be injected into only
the authorized Unity process and worker. It must not be committed to the repository,
placed in a URL or passed as a command-line argument.

## 10. Known limitations and unverified assumptions

### Python foundation

- The components are not yet joined by a durable asynchronous workflow executor.
- The journal has no schema migration framework.
- SQLite contention and crash recovery have not been load-tested.
- Provider measurements are supplied data; no metrics ingestion service exists.
- The scheduler returns decisions but does not apply cgroups, systemd scopes or process
  suspension.
- The hardware profiler is incomplete for GPU vendors, thermal sensors and real-time
  application discovery.
- The authorization types are primitives, not a signed grant service.
- Audit rotation, integrity chaining, export and retention are not implemented.

### Unity package

- C# compilation has not been run in Unity.
- Unity 6.0 patch versions and later Unity 6 releases require a compatibility matrix.
- HttpListener behavior and port binding require validation on the PyFlare Ubuntu image.
- Only one editor can bind the fixed port; multi-editor discovery is not implemented.
- The token is shared for the bridge process; per-request signed grants are not yet
  verified by the Editor package.
- The project_id is required but is not yet cryptographically bound to the opened Unity
  project.
- Idempotency records live in Library and disappear when Library is deleted.
- There is still a small crash window between a Unity mutation and idempotency record
  persistence.
- New unsaved scenes are rejected because they cannot provide a stable GlobalObjectId.
- Scene saving, components, prefabs, asset imports, Console inspection, Play Mode,
  tests and builds are not implemented.
- Request cancellation after the worker disconnects is not implemented.
- Main-thread work is bounded per update, but operation-specific time budgets and
  profiling remain planned.

### Whole platform

- Jarvis, natural-language TaskSpec generation, context memory, knowledge graph,
  Blender, asset registry, code workspaces, distributed workers and OS service
  packaging remain separate future projects.
- No claim of autonomous Unity control or production readiness is justified yet.
- The existing ISO/build scripts were not rebuilt in this pass.

## 11. Recommended next implementation order

### Milestone 1 — Compile the Unity package

1. Create a disposable Unity 6 test fixture under a separate test project.
2. Pin exact Unity editor versions for the supported matrix.
3. Run batchmode compilation and capture Editor.log.
4. Add Edit Mode tests for token rejection, state inspection, saved-scene requirement,
   GameObject creation, parent resolution, Undo and idempotency conflict.
5. Benchmark editor-update queue latency and GlobalObjectId operations.
6. Decide whether HttpListener is retained or replaced by named pipes or a Unix domain
   socket after Ubuntu measurements.

Acceptance: no C# errors, deterministic responses and correct Undo behavior on the
supported editor matrix.

### Milestone 2 — Join the primitives into one execution service

1. Accept TaskSpec v1 through a local authenticated API.
2. Create the journal task.
3. Validate a signed task-scoped grant.
4. Capture live hardware.
5. Route and admit deterministically.
6. Reserve an idempotency key.
7. Invoke one registered worker.
8. Run mandatory validators.
9. Persist result, evidence, timing and route choice.
10. Apply bounded retry or move to human review.

Acceptance: one read-only Unity state task survives restart and produces a complete
audit trail.

### Milestone 3 — Safe Unity write workspace

1. Create an isolated Git worktree or task workspace.
2. Bind project_id to the canonical project root and parent commit.
3. Add Console inspection and compilation-state operations.
4. Add component inspection and mutation using SerializedObject.
5. Add explicit diff generation and human approval before save or merge.
6. Add Unity Test Framework and Play Mode validation.

Acceptance: create a GameObject and attach a controlled component in a task workspace,
validate it, show the diff and leave main untouched.

### Milestone 4 — Project knowledge

Implement evidence storage, memory state transitions, file/commit/hash invalidation,
targeted retrieval and relationship graph updates. Do not store complete agent
conversations as project truth.

### Milestone 5 — Asset and Blender vertical slice

Add an immutable content-addressed asset registry, version metadata, validation results
and one bpy-based Blender worker feeding a Unity import validator.

Distributed studio scheduling should remain later; reliable authenticated local work is
the prerequisite.

## 12. Handoff checklist

- [x] Work isolated from main.
- [x] Pull request remains open.
- [x] Master architecture plan preserved in the repository.
- [x] New Python code linted.
- [x] 31 Python tests passed.
- [x] Unity package clearly marked experimental.
- [x] No credentials committed.
- [x] Mutating Unity operation requires Undo.
- [x] Automatic scene saving rejected.
- [x] Current limitations recorded.
- [ ] Unity package compiled in a real editor.
- [ ] End-to-end control-plane-to-Unity test passed.
- [ ] Human code review completed.
- [ ] Pull request approved and merged.

## 13. Final engineering note

The architectural center remains unchanged:

PyFlare is not one AI doing everything. It is an operating environment that coordinates
the smallest capable intelligence, deterministic tool, development application and
hardware resource for each task while preserving bounded authority and shared,
validated, version-aware project knowledge.

This implementation moves that idea from documentation into testable foundations, but
the boundary between foundation and complete platform must remain explicit.
