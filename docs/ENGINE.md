# AppSuite Ecosystem — Engine & Orchestration

**Version:** 1.0.0 | **Status:** Production | **Author:** Aachman Studios | **Last Updated:** 2026-08-04

---

## GraphOrchestrator

**File:** `appsuite/engine/orchestrator.py` (19 KB)

`GraphOrchestrator` is the production-grade parallel DAG execution engine for AppSuite Jarvis. It handles parallel execution, cycle detection, deadlock detection, resource gates, priority scheduling, timeout protection, checkpointing, and observability.

---

## `run_dag()` — Parallel DAG Execution

```python
def run_dag(
    self,
    agent_tasks: list,        # List of AgentTask objects with dependencies
    job_state: Dict,          # Shared UnifiedJobState
    hardware=None,            # HardwareManager for resource monitoring
    worker_scores=None        # Optional dict of agent_type → performance score
) -> list:                    # Returns list of AgentResult
```

### Execution Algorithm

```
1. _detect_cycles(agent_tasks)        DFS cycle detection — raises ValueError on cycle
2. Load checkpoint (if crash recovery)
3. ThreadPoolExecutor(max_workers=4)
4. WHILE pending_tasks OR running_tasks:
   a. Find ready tasks (all dependencies in completed_tasks)
   b. Deadlock check: if ready=0 and pending>0 and running=0 → RuntimeError
   c. Sort ready by: priority + worker_score - (estimated_duration / 120)
   d. For each ready task:
      - Resource check: RAM > 80% → pause GPU tasks 15s, then run anyway
      - Submit agent.run(task, job_state) to ThreadPoolExecutor
      - EventBus.publish(TaskStarted)
   e. Collect completed futures:
      - success → completed_tasks.add(task_id), CheckpointManager.save()
      - timeout (5min) → AgentResult(status="failed", error="TASK_TIMEOUT")
      - exception → AgentResult(status="failed", error=str(exc))
   f. On failure → raise RuntimeError (caught by StateGraph reflect_node)
5. EventBus.publish(PipelineFinished)
6. CheckpointManager.cleanup(job_id)
7. Return results
```

---

## `run()` — Legacy Sequential Execution (Deprecated)

`GraphOrchestrator.run()` is the legacy sequential execution path used by `Pipeline.execute()` in graph-orchestrator mode. New code must use `run_dag()`.

It is deprecated as of the Jarvis v1 architecture and will be removed in a future release.

---

## Job State

**File:** `appsuite/engine/job_state.py` (3.6 KB)

`UnifiedJobState` is the shared state object passed through the entire execution graph:

```python
class UnifiedJobState(dict):
    """Shared mutable state for a job. Dict subclass for LangGraph compatibility."""
    assets: list              # Downloaded/discovered 3D assets
    normalized_assets: list   # Format-normalised assets
    scene_layout: dict        # Blender scene description
    godot_project: str        # Path to Godot project
    main_scene: str           # Path to main .tscn
    deployment_url: str       # Live deployment URL
    stages: dict              # Per-stage results
    history: list             # Visited node names
    world_model: WorldModel   # Environment awareness
    project: Project          # Current project workspace
```

---

## Event Bus

**File:** `appsuite/engine/event_bus.py` (2.4 KB)

The engine publishes typed events for observability:

| Event | When |
|---|---|
| `TaskCreated` | AgentTask registered |
| `TaskStarted` | Worker begins execution |
| `TaskCompleted` | Worker succeeded |
| `TaskFailed` | Worker failed |
| `WorkerStarted` | Individual worker start |
| `WorkerFinished` | Individual worker end |
| `CheckpointSaved` | State snapshot saved |
| `RecoveryStarted` | Resuming from checkpoint |
| `RecoveryCompleted` | Checkpoint restore complete |
| `ResourceWarning` | RAM/CPU/GPU threshold exceeded |
| `PipelineFinished` | All tasks complete |

---

## Checkpoint Manager

**File:** `appsuite/engine/checkpoint.py` (2 KB)

Saves and restores execution state after each successful task:

```python
# Save after each successful task
ckpt_path = checkpoint_mgr.save(
    job_id, completed_tasks, set(pending_tasks.keys()), pipeline_state
)

# On restart, resume from last checkpoint
ckpt_data = checkpoint_mgr.load(job_id)
if ckpt_data:
    completed_tasks = set(ckpt_data["completed"])
    # Skip already-completed tasks
```

Checkpoints are stored in a platform-appropriate temp directory (not CWD-relative, fixing the W6 bug).

---

## Observability

**File:** `appsuite/engine/observability.py` (7.3 KB)

`ObservabilityWriter` tracks during execution:
- Peak RAM percentage
- Peak CPU percentage
- Per-task execution durations
- Pipeline start time and total duration

All data is surfaced via `EventBus` and queryable via the FastAPI dashboard.

---

## Pipeline

**File:** `appsuite/pipeline/pipeline.py` (23 KB)

`Pipeline.execute()` is the legacy worker chain, called by `JarvisCore` when agent_tasks are empty (non-LangGraph path):

```
internet → analysis → blender → godot → validation → deploy
```

In the modern LangGraph path, each of these workers is invoked by its corresponding agent via `run_dag()`.

---

## Related Documents

| Document | Purpose |
|---|---|
| [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) | Full Jarvis architecture |
| [ORCHESTRATION.md](ORCHESTRATION.md) | Agent coordination |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview |
