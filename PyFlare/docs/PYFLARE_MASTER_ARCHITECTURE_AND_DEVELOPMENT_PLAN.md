# PyFlare Master Architecture & Development Plan

**Organization:** Aachman Studios  
**Architecture baseline:** 1.0  
**Primary game engine:** Unity  
**Base platform:** Ubuntu 24.04 LTS, Linux, GNOME 46  
**Document date:** 2026-09-14  
**Maturity:** Long-term architecture with an early implementation foundation

## 1. Document purpose

This document is the engineering baseline for PyFlare. It defines the intended product, subsystem boundaries, data contracts, control flow, validation rules, implementation order and acceptance gates.

PyFlare is not an AI Linux distribution, chatbot, coding assistant or generic multi-agent framework. It is intended to become an AI-native, hardware-aware software and game-development operating environment. Developer intent is converted into coordinated, validated work across models, deterministic tools, development applications, compute, project memory, code, assets and potentially multiple computers.

The durable architecture is the control plane, protocols, registries, policies, evidence system and version-aware project knowledge. Models and service providers are replaceable workers.

## 2. Non-negotiable principles

1. Hardware should limit execution speed, not ambition.
2. Developer intent should remain stable while execution strategy adapts.
3. Final routing authority belongs to deterministic software.
4. The smallest reliable capability should handle each task.
5. The strongest model is not automatically the correct provider.
6. Sometimes the correct AI is no AI.
7. Models may recommend routes but may not authorize themselves.
8. Workers receive bounded task-specific permissions.
9. Only the assigned executor normally writes task-owned files.
10. Generated work remains untrusted until validation succeeds.
11. Share structured project knowledge, not complete agent conversations.
12. AI findings require evidence before becoming project truth.
13. Context must be relevant, compressed, structured and version-aware.
14. Foreground development responsiveness outranks background intelligence.
15. Unity is the primary engine automation target.
16. Blender remains a first-class asset creation and processing capability.
17. Code and large binary assets require different version strategies.
18. Consumer PyFlare adapts automatically to available resources.
19. Distributed studio execution must not be built before local reliability.
20. Every meaningful automated action must be explainable and auditable.

## 3. Status vocabulary

Every subsystem and claim uses one of these states:

- **VERIFIED FOUNDATION:** implementation and explicit tests exist.
- **EXPERIMENTAL:** a prototype exists but is not proven reliable.
- **PLANNED:** accepted design without complete implementation.
- **RESEARCH:** design or feasibility remains unresolved.
- **DEPRECATED:** implementation is being removed from the primary architecture.
- **BLOCKED:** progress requires an external dependency or decision.

A directory, placeholder UI or architectural document is not proof of implementation.

## 4. Current baseline

| Subsystem | Status | Qualification |
| --- | --- | --- |
| Ubuntu/GNOME image scaffolding | VERIFIED FOUNDATION | Build, filesystem, branding and validation scripts exist |
| Desktop applications | EXPERIMENTAL | Several application entry points remain stubs |
| Browser agent | EXPERIMENTAL | Previously reported complete; requires capability and security verification |
| Knowledge graph | EXPERIMENTAL | Previously reported complete; schema and version behavior require verification |
| TaskSpec | VERIFIED FOUNDATION | Typed contract and JSON Schema in control_plane |
| Capability/provider registries | VERIFIED FOUNDATION | Deterministic duplicate-safe registries |
| Deterministic router | VERIFIED FOUNDATION | Hard filters, scoring explanations and fallbacks |
| Resource scheduler | VERIFIED FOUNDATION | Admission and policy decisions; no process controller |
| Task permissions | VERIFIED FOUNDATION | Capability and filesystem scope primitives |
| Audit trail | VERIFIED FOUNDATION | Append-only JSONL sink and secret redaction |
| Unity protocol | VERIFIED FOUNDATION | Transport-neutral contracts and editor-state gate |
| Unity Editor bridge | PLANNED | Editor extension and IPC not implemented |
| Godot primary automation | DEPRECATED | May later exist only as an optional plugin |
| Context Manager | PLANNED | No verified version-aware memory service |
| Blender worker | PLANNED | No verified structured bpy worker |
| Asset registry | PLANNED | No verified immutable asset service |
| Distributed studio | RESEARCH | Delayed until single-node execution is reliable |

## 5. Complete system architecture

    Developer
        |
      Jarvis
        |
    Task Understanding
        |
    Validated TaskSpec
        |
    +---------------------------------------+
    | Deterministic Router                  |
    | Workflow Engine                      |
    | Resource Scheduler                   |
    | Authorization and Security           |
    | Distributed Context Manager          |
    +---------------------------------------+
        |
    Capability Registry
        |
    +---------------------------------------+
    | Deterministic tools                  |
    | Local and cloud models               |
    | Unity and Blender                    |
    | Compilers and test runners           |
    | Browser and package tools            |
    | Version control and asset services   |
    | Remote workstations                  |
    +---------------------------------------+
        |
    Specialized bounded workers
        |
    Execution -> Validation
        |
    Code VCS + Asset Registry + Artifacts
        |
    Evidence and Project Knowledge
        |
    Future tasks

### 5.1 Architectural planes

**Experience plane**

- Jarvis text, voice and desktop interface
- CLI
- IDE and Unity surfaces
- Progress, approval and result presentation

**Control plane**

- Task understanding
- TaskSpec validation
- Deterministic routing
- Workflow planning
- Resource admission
- Authorization
- Retry and fallback control

**Knowledge plane**

- Evidence store
- Structured memories
- Knowledge graph
- Retrieval and version invalidation
- Audit records

**Execution plane**

- Deterministic workers
- Local/cloud model workers
- Unity Worker and Unity Bridge
- Blender Worker
- Browser Worker
- Compiler and test workers
- Asset and version-control workers
- Remote node agents

**Project-state plane**

- Git repositories and task workspaces
- Asset Registry
- Artifact store
- Build outputs
- Validated project knowledge

## 6. Component ownership boundaries

| Component | Owns | Must not own |
| --- | --- | --- |
| Jarvis | Interaction, clarification and progress | Final routing or unrestricted execution |
| Task Understanding | Intent normalization | Tool execution |
| Router | Provider filtering, scoring and fallback order | Resource reservations or permissions |
| Scheduler | Resource budgets, queues and preemption | Semantic provider suitability |
| Workflow Engine | DAG execution and task lifecycle | Provider reputation rules |
| Capability Registry | Capability contracts | Credentials |
| Provider Registry | Provider properties and measured results | Raw secrets |
| Authorization | Scoped grants and approval policy | Planning |
| Context Manager | Evidence-bearing project memories | Complete chat archives |
| Knowledge Graph | Versioned entity relations | Treating inference as proof |
| Audit Service | Append-only action history | Mutable operational state |
| Unity Worker | Structured Unity operations | General host control |
| Blender Worker | Structured bpy operations | Merge approval |
| Validators | Evidence and verdicts | Hidden repair outside the task |
| Asset Registry | Immutable assets and metadata | Source-code history |
| Node Agent | Sandboxed local execution | Global scheduling authority |

## 7. Core message envelope

All internal commands and events use versioned envelopes:

    {
      "schema": "pyflare.task-command/v1",
      "message_id": "msg_...",
      "correlation_id": "task_18429",
      "causation_id": "step_04",
      "created_at": "ISO-8601 UTC",
      "deadline_at": null,
      "sender": "workflow-engine",
      "recipient": "unity-worker",
      "idempotency_key": "task_18429:step_04:attempt_1",
      "payload": {}
    }

Initial transport uses JSON and JSON Schema. Binary encoding may be introduced only after profiling, without changing semantic contracts. IDs should be sortable UUIDv7 or ULID values.

## 8. TaskSpec

TaskSpec is the immutable, validated description of intended work. It contains:

- Task and project identifiers
- Original request reference and normalized summary
- Domain and operation
- Required capabilities
- Expected outputs and acceptance criteria
- Read/write/tool/network scopes
- Privacy, cost, latency and deadline constraints
- CPU, RAM and VRAM budgets
- Required validators
- Parent commit, file hashes and application versions
- Human-approval conditions

Pipeline:

1. Jarvis captures the request.
2. A parser creates a candidate TaskSpec.
3. Schema validation rejects malformed output.
4. Deterministic enrichment resolves project paths and installed capabilities.
5. Policy validation removes or rejects unauthorized requirements.
6. Material ambiguity returns to the developer.
7. The accepted revision becomes immutable.
8. Later changes create a new revision.

An LLM may propose TaskSpec fields. It may not authorize or silently accept them.

## 9. Capability and provider registries

A capability defines what can be done. A provider defines what can perform it.

A capability manifest declares:

- Stable ID and semantic version
- Input/output schema
- Side effects
- Required permissions
- Supported platforms
- Resource profile
- Offline support
- Concurrency and workspace rules
- Validation requirements
- Reversibility and idempotency
- Expected failure codes
- Health-check interface

A provider record declares:

- Provider identity and execution kind
- Capabilities
- Runtime requirements
- RAM and VRAM estimates
- Cost model
- Privacy class
- Network dependency
- Required applications
- Availability and circuit state
- Measured capability-specific history
- Exact model/artifact/runtime versions

Registration means discoverability, not trust. Plugins begin disabled or minimally permissioned.

## 10. Deterministic router

### 10.1 Pipeline

    TaskSpec
      -> resolve capability requirements
      -> build candidate set
      -> hard filtering
      -> deterministic scoring
      -> execution-plan construction
      -> budget simulation
      -> primary route and ordered fallbacks
      -> authorization

### 10.2 Hard filters

A candidate is rejected for:

- Missing capability
- Schema or version incompatibility
- Insufficient absolute or current resources
- Privacy violation
- Cost above budget
- Provider unavailability
- Missing application or runtime
- Missing connectivity
- Insufficient model context
- License/platform incompatibility
- Unavailable permissions
- Open reliability circuit breaker
- Impossible deadline
- Project-policy denial

A high score cannot override a hard filter.

### 10.3 Scoring

Surviving candidates receive normalized component scores for:

- Capability-specific measured quality
- Historical success
- Latency fitness
- Cost fitness
- Resource headroom
- Privacy fitness
- Availability
- Deterministic-tool preference
- Workstation-interference penalty

Model self-reported confidence is weak evidence and must be capped. Compilers, tests, validators and measured task history dominate brand reputation.

Route output records the selected provider, fallbacks, rejected candidates, reasons, score components, policy version and hardware snapshot.

Weights and gates require benchmarking. They must not be selected from marketing claims.

## 11. Resource scheduler

The router decides what should perform work. The scheduler decides where and when it may execute.

Priority classes:

1. Interactive critical
2. Foreground assist
3. Background normal
4. Batch heavy
5. Maintenance

Admission requires requested resources plus reservations plus a safety margin to fit within live availability.

Managed resources:

- CPU shares
- RAM and swap pressure
- VRAM and GPU load
- Disk space and I/O
- Network and metering state
- Thermal headroom
- Application exclusivity
- Unity compile/import state

Degradation order:

1. Deterministic tool
2. Smaller local model
3. Smaller context or batch
4. CPU instead of GPU where practical
5. Lower preview quality
6. Pause preemptible background work
7. Cloud provider
8. Trusted remote node
9. Queue
10. Ask the developer when cost or result materially changes

## 12. Hardware profiler

Static HardwareProfile stores CPU, threads, total memory, GPU, storage, drivers, installed applications and runtimes.

Live ResourceSnapshot stores currently available RAM/VRAM, load, foreground application, thermal state, disk space, connectivity and provider health.

Unknown sensor data remains unknown, never zero. Profiling failures trigger conservative policies.

Profiles should be based on measured performance, not only hardware model names.

## 13. Workflow engine and task ownership

Complex requests compile into a directed acyclic graph. Each step declares:

- One executor
- Optional read-only reviewers and observers
- Inputs and expected outputs
- File and asset leases
- Resource budget
- Retry budget
- Validators
- Cancellation and compensation behavior

Task lifecycle:

    DRAFT -> AUTHORIZED -> QUEUED -> RUNNING -> VALIDATING
      -> COMPLETED -> MERGED

Failure branches:

    RUNNING/VALIDATING -> RETRYING -> QUEUED
    VALIDATING -> REVIEW_REQUIRED -> FAILED or revised task
    RUNNING -> CANCELLED

Only the executor receives write authority. Reviewers inspect snapshots.

Substantial tasks run in Git worktrees or isolated copies, not directly on the active branch.

## 14. Security and permissions

Security layers:

1. User identity
2. Project membership
3. Task authorization
4. Capability permission
5. Scoped short-lived execution token
6. OS sandbox
7. Network policy
8. Secrets broker
9. Audit trail
10. Validation and merge gate

Permissions include READ, WRITE, EXECUTE, NETWORK, INSTALL and SYSTEM_CHANGE.

Grants bind:

- Task
- Worker identity
- Capabilities
- Project-root-relative paths
- Denied paths
- Network domains
- Expiry and maximum uses

Workers receive secret handles, not secret values in prompts. The broker injects values only into authorized processes and redacts outputs.

Candidate sandboxing technologies include AppArmor, systemd isolation, Flatpak portals, Bubblewrap/containers, filesystem namespaces and separate service users. Unity and Blender require broader access than simple scripts, so their bridges require strict project roots, authenticated local communication and detailed auditing.

Webpage, documentation and repository content is untrusted data and may never change policy or grant permissions.

## 15. Unity Automation Layer

Unity replaces Godot as the primary engine target.

Flow:

    Workflow Engine
      -> Unity Worker
      -> authenticated local Unity Bridge
      -> Unity Editor APIs
      -> structured response
      -> validators

### 15.1 Unity Editor package

The Unity package should contain:

- Command dispatcher
- Versioned operation handlers
- Editor-state observer
- Object identity service
- Console collector
- Test/build adapters
- Undo/transaction adapter
- Schema validator
- Local authenticated transport
- Health endpoint and event stream
- Persistent operation journal for domain reload

### 15.2 Transport

Prototype with localhost HTTP if necessary. Production Linux should prefer Unix domain sockets; Windows can use named pipes. WebSocket may provide events after the request/response protocol is stable.

Localhost transport binds only to loopback, rejects browser-origin requests and uses short-lived scoped authentication.

### 15.3 Unity commands

Every command includes protocol version, task/project/request IDs, operation, structured arguments, preconditions, idempotency key and explicit save/undo options.

Preconditions can require:

- Edit or Play Mode
- Compilation idle
- Asset database idle
- Exact scene path and hash
- Expected object/component version

### 15.4 Safety rules

- Reject edit-only changes during Play Mode.
- Wait for compilation/import with deadlines.
- Use Unity Undo APIs where practical.
- Group operations transactionally.
- Snapshot serialized objects before mutation.
- Avoid direct prefab/scene YAML editing by default.
- Save only when authorized.
- Persist in-flight state across domain reload.
- Reconcile state after editor restart.
- Detect duplicate idempotency keys.

### 15.5 Validation ladder

1. Command schema
2. Authorization and preconditions
3. Operation completion
4. Expected object/component state
5. Serialization
6. C# compilation
7. Console policy
8. Edit Mode tests
9. Play Mode tests or smoke scenario
10. Performance budget
11. Allowed workspace diff

GUI clicking is an experimental last resort for unsupported UI, never the main control system.

## 16. C# pipeline

Components:

- Roslyn symbol index
- Syntax-aware edit engine
- Unity API/version knowledge
- Assembly-definition resolver
- Package dependency resolver
- Formatter and analyzers
- Diagnostic normalization
- Edit/Play Mode test generation
- Unity Console correlation
- Diff and impact analysis

Pipeline:

    relevant context
      -> change plan
      -> symbol-aware edit
      -> format/static analysis
      -> compile
      -> tests
      -> diff validation
      -> evidence and memory extraction

The system must understand Unity lifecycle rules, serialization, main-thread restrictions, domain reload, prefab overrides and assembly boundaries.

## 17. Blender and adaptive 3D

Structured Blender work should use bpy rather than mouse coordinates.

Pipeline:

    asset request
      -> route generation capability
      -> Blender processing
      -> geometry/material validation
      -> optimization
      -> export
      -> Asset Registry
      -> Unity import
      -> prefab construction
      -> Unity validation

Validation includes readability, bounds, geometry budgets, topology, UVs, texture references, material slots, scale, axes, rig structure, animations, naming, round-trip import and license/source metadata.

Procedural Blender generation is suitable only for some asset categories. Category-level cost and quality require benchmarks.

## 18. Asset Registry

Separate:

- Metadata database
- Content-addressed immutable object store
- Local workstation cache
- Project asset-version bindings

Every asset version records:

- Stable asset ID
- Version
- SHA-256 blob hashes
- Formats
- Source and generating task
- Dependencies
- Validation results
- Approval state
- Current/rejected/superseded state
- License metadata

Never overwrite a validated asset. Create a new immutable version and preserve the reason failed versions were rejected.

Distributed storage uses a central object store plus registry and lazy local cache. Workspace manifests pin exact versions. Leases prevent eviction during active tasks. Chunked transfers are verified and atomically finalized.

Git LFS may provide an initial binary transport but is not the complete registry.

## 19. Code versioning

Use Git first. Do not build a new source-control engine early.

Initial layer:

- Git for code and small metadata
- Worktrees or isolated clones per task
- Asset manifests referencing registry versions
- PyFlare records linking tasks, commits, assets and validation

Every proposed merge contains a change manifest with base/result commits, files, assets, validation, approvals and merge risk.

Authentication, dependencies, build settings, project-wide refactors, destructive asset changes, secrets and deployments require high-impact approval policy.

## 20. Context Manager

Use three coordinated stores:

1. Immutable evidence store for logs, tests, diffs and artifacts
2. Structured memory store for claims, decisions, warnings and results
3. Knowledge graph for project relationships

Vector search may accelerate retrieval but is not authoritative.

Memory types include FACT, FINDING, DECISION, WARNING, DEPENDENCY, TASK_STATE, UNVERIFIED_CLAIM, FAILURE, PERFORMANCE_RESULT, ASSET_INFORMATION, ARCHITECTURAL_RULE and VERSION_INFORMATION.

Every record includes subject, predicate/value, provenance, evidence references, status, confidence, commit/file hashes, timestamps and supersession links.

Validation lifecycle:

    UNVERIFIED -> SUPPORTED -> VALIDATED -> ACTIVE

Alternative states:

    REJECTED, SUPERSEDED, INVALIDATED

When related code changes, memories scoped to old hashes lose retrieval eligibility and may be queued for revalidation. Historical records remain available for explanation.

## 21. Context retrieval and knowledge graph

Candidate retrieval uses:

- Exact entity/symbol matches
- Dependency neighbors
- File and scene relations
- Semantic similarity
- Recent task history
- Similar previous failures
- Architectural decisions

Ranking combines relevance, validation, version compatibility, source quality, dependency distance and recency.

The context package contains only the task summary, relevant excerpts, active rules, dependencies, previous failures, acceptance criteria and evidence references.

Graph entities include projects, commits, files, symbols, packages, scenes, GameObjects, components, prefabs, materials, textures, models, animations, asset versions, tasks, tests, builds, decisions, workers and providers.

Graph edges carry provenance, confidence and version scope. Inferred edges cannot silently become validated facts.

Start with a relational database plus explicit relation tables. Adopt a graph database only if benchmarks justify it.

## 22. Validation and self-healing

Every validator returns PASS, FAIL, INCONCLUSIVE or SKIPPED plus structured findings, evidence, tool/version, tested scope, reproduction data, duration and cost.

SKIPPED never means PASS.

Retry policy:

- Transient transport failure: bounded backoff
- Resource exhaustion: reschedule or reroute
- Invalid structured output: one constrained repair, then fallback
- Compile/test failure: retrieve diagnostics and revise
- Capability mismatch: reroute
- Permission denial: stop for approval
- Repeated identical failure: open circuit and escalate
- Inconclusive validation: stronger validator or human review

Every task has attempt, token, cost, time and mutation limits. Self-healing is an audited task loop, not permission to silently modify the operating system.

## 23. Browser and research worker

Flow:

    research request
      -> policy/domain check
      -> search/fetch
      -> extraction
      -> claim/evidence mapping
      -> freshness/authority scoring
      -> task-local context
      -> optional validated memory

Record URL, retrieval timestamp, content hash, source version and licensing. Downloads are scanned and validated before entering the project. Downloaded code is never executed automatically.

## 24. Screen understanding

Status: RESEARCH/EXPERIMENTAL.

Prefer direct state before vision:

1. Unity Bridge
2. IDE/LSP
3. Window metadata
4. Accessibility APIs
5. OCR
6. Small local vision
7. Cloud multimodal escalation

Raw capture is disabled for sensitive applications, processed locally by default, visibly indicated and not retained unless explicitly required. Compact observations expire unless validated and relevant.

## 25. Offline behavior

Without connectivity:

- OS, local projects, Unity, Blender, code and tests remain usable.
- Jarvis exposes only available local capabilities.
- Project memory and graph remain accessible.
- Cloud/remote tasks enter WAITING_FOR_CONNECTIVITY.
- Research queues without retry storms.
- Asset work uses pinned cache versions.
- Audit data spools locally and syncs later.
- The UI shows reduced capability honestly.

## 26. Consumer profiles

**Low resource**

- One lightweight worker
- Aggressive unloading
- Minimal background services
- No continuous vision
- Deterministic tools and cloud fallback
- Reduced preview quality

**Balanced**

- Hybrid local/cloud routes
- Moderate concurrency
- Selective background indexing
- Idle-time processing

**High resource**

- Larger local models
- Concurrent read-only reviewers
- Local generation where benchmarked
- Higher preview quality

Profiles derive from live benchmarks and can temporarily downgrade under load.

## 27. PyFlare Studio

Future studio components:

- Coordinator
- Node registry
- Distributed queue
- Shared asset/artifact store
- Shared project memory
- Node identity and certificates
- Health service
- Cache-locality planner

Distributed scheduling considers GPU/RAM, workloads, installed tools/models, cached assets, priority, duration and transfer cost.

Remote commands require mutual authentication, signed grants and encrypted transport. Studio work is blocked until local idempotency, recovery and artifact handling are reliable.

## 28. Auditability

Record:

- Task and initiating user
- Executor/model/provider
- Route scores and rejected candidates
- Tools and versions
- Permissions and approvals
- Files/assets changed
- Validators and evidence
- Cost and duration
- Failures, retries and fallback routes
- Merge result

A developer must be able to answer what changed, what changed it, why, under which authority and with what validation.

## 29. Complete Unity enemy example

Request:

"Create an enemy character that patrols the environment, detects the player, attacks at close range and has animations."

Decomposition:

- Character asset
- Rig
- Animation clips
- Behavior architecture
- C# implementation
- Detection
- Navigation
- Melee combat
- Unity prefab
- Tests
- Performance validation

Possible routes:

- Asset generation provider for the character
- Blender for cleanup, rig and export
- Reasoning worker for behavior architecture
- Coding worker for C#
- Unity Worker for scene, prefab and NavMesh work
- Unity Test Runner for Edit/Play Mode validation
- Profiler validator for resource budgets

Context retrieval supplies only current enemy architecture, player APIs, code conventions, Unity version, navigation/animation standards, performance budget and previous enemy failures.

Validated code enters Git. Validated binaries enter the Asset Registry. Findings enter memory with version scope.

## 30. Failure scenarios

| Failure | Required behavior |
| --- | --- |
| Unity compiling | Queue incompatible commands |
| Unity crash | Reconcile task journal and idempotency keys |
| Invalid model JSON | Repair once, then fallback |
| Cloud outage | Circuit breaker and alternate route |
| Low RAM | Pause work, unload model or reroute |
| VRAM exhaustion | Protect desktop; queue or change route |
| Corrupt asset | Reject hash and resume verified chunks |
| Out-of-scope write | Terminate worker and quarantine output |
| Flaky test | INCONCLUSIVE, never pass |
| Stale memory | Prefer code/test evidence |
| Conflicting tasks | File leases, serialization or rebase |
| Remote-node loss | Requeue only idempotent/checkpointed work |
| Prompt injection | Treat content as data; no authority change |
| Low disk | Stop downloads/builds safely |
| Validator crash | Alternate validator or human review |

## 31. Testing strategy

**Unit:** schemas, filters, scoring determinism, permissions, memory states, invalidation, retry limits and redaction.

**Contract:** worker envelopes, capability manifests, Unity Bridge, Blender Worker, providers, secret broker and remote protocol.

**Integration:** intent-to-workspace route, C# compile/test, Blender-to-Unity asset import, memory retrieval, offline fallback and remote loss.

**System:** reference projects with known rename, compile repair, MonoBehaviour, prefab, asset import, Play Mode and interrupted-task cases.

**Security:** traversal, symlink escape, injection, secret leakage, replay, malicious plugin, forged worker, network bypass and hostile archives.

**Performance:** realistic Unity workloads across 8 GB, balanced and high-resource machines.

## 32. Implementation phases

### Phase 0: inventory and architecture

- Audit repository
- Verify existing claims
- Freeze schemas
- Remove Godot assumptions
- Define acceptance tests and ADRs
- Establish threat model

Exit: verified component map and reproducible baseline.

### Phase 1: deterministic single-machine control plane

- TaskSpec
- Registries
- Router
- Hardware snapshot
- Scheduler
- Task journal
- Scoped permissions
- Audit
- CLI and tests

Exit: reproducible deterministic routing and admission.

### Phase 2: Unity vertical slice

- Editor package
- Authenticated local transport
- Scene/GameObject/component operations
- C# creation and attachment
- Compile/Console observation
- Edit and Play Mode tests
- Undo, idempotency and task workspace

Exit: one small Unity feature created and validated without coordinate clicking.

### Phase 3: context and knowledge

- Evidence store
- Memory lifecycle
- Symbol/entity graph
- Version invalidation
- Retrieval budgets
- Structured findings

Exit: workers receive relevant version-compatible context.

### Phase 4: Blender and assets

- bpy worker
- Asset validation
- Content-addressed store
- Metadata/versioning
- Unity import
- Local cache

Exit: asset passes Blender, Registry and Unity validation.

### Phase 5: hybrid model manager

- Catalog
- Resumable verified downloads
- Runtime adapters
- Compatibility benchmarks
- Load/unload scheduling
- Cloud policy
- Escalation measurements

Exit: routes adapt safely across hardware tiers.

### Phase 6: reliability and security

- Sandboxes
- Secrets broker
- Circuit breakers
- Crash recovery
- Replay protection
- Fault and adversarial tests
- Update rollback

Exit: failures cannot corrupt the main project or expose secrets.

### Phase 7: consumer OS integration

- Ubuntu image
- GNOME experience
- Installer and first-run profiler
- Package/plugin manager
- On-demand service activation
- Recovery and signed updates

Exit: low-overhead clean install and recoverable upgrades.

### Phase 8: studio distribution

- Node identity
- Distributed scheduler
- Shared registries
- Cache-aware placement
- Remote recovery

Exit: worker loss does not lose state or duplicate committed work.

## 33. Highest risks

1. Scope exceeds what can be implemented simultaneously.
2. Unity domain reload/import behavior breaks naive automation.
3. AI resource use makes low-end development unusable.
4. Generated changes damage projects without isolation.
5. Stale memory becomes false project truth.
6. Asset storage grows without lifecycle controls.
7. A custom VCS distracts from proving execution.
8. Plugins expand the attack surface.
9. Model, asset and Unity licensing conflict.
10. Distributed execution multiplies immature local failures.
11. Router metrics optimize latency instead of reliable outcomes.
12. Self-healing hides unapproved changes.

## 34. Unresolved research

- Best local Unity/C# models per hardware tier
- Reliable low-cost local visual understanding
- Stable Unity object identity across reload/version operations
- Transactional Unity rollback across import and domain reload
- Asset categories suitable for procedural Blender generation
- Relational/vector versus dedicated graph storage
- Safe adaptive router-weight updates
- Shared-memory GPU profiling
- Unity-compatible sandbox boundaries
- Generated-asset licensing enforcement
- Distributed-memory consistency
- Large-asset remote transfer strategy
- Safe Ubuntu point-release maintenance
- Full ISO versus installable platform layer

These require prototypes and benchmarks. They are not solved features.

## 35. Immediate implementation order

The next work should remain narrow:

1. Make the Phase 1 control-plane CI fully green.
2. Add serialized TaskSpec loading and strict schema validation.
3. Add task journal and deterministic workflow state machine.
4. Build a minimal Unity Editor package.
5. Implement one authenticated, idempotent operation: inspect editor state.
6. Implement one reversible mutation: create a GameObject without saving.
7. Add compile/Console validation.
8. Run the vertical slice against a tiny reference Unity project.
9. Only then expand to C# editing, prefabs and tests.

## 36. First product acceptance gate

PyFlare's central idea is proven only when this works end to end:

    developer request
      -> validated TaskSpec
      -> deterministic route
      -> scoped authorization
      -> resource admission
      -> isolated workspace
      -> structured Unity/C# operation
      -> deterministic validation
      -> evidence
      -> proposed merge

OS branding, a chatbot UI, many agents or a large model do not substitute for this gate.

## 37. Final architecture statement

PyFlare is not one AI doing everything. It is an operating environment that coordinates the appropriate intelligence, deterministic tool, development application and hardware resource for each task while maintaining shared, validated and version-aware project knowledge.
