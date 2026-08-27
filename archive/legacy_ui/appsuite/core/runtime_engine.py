import time
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
import psutil

from ..logging_setup import get_logger
from .event_bus import EventBus
from .crash_manager import CrashManager

log = get_logger("runtime_engine")

class RuntimeState(Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    SEARCHING_ASSETS = "searching_assets"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"
    BLENDER_PROCESSING = "blender_processing"
    GODOT_IMPORT = "godot_import"
    CODE_GENERATION = "code_generation"
    VALIDATION = "validation"
    REPAIRING = "repairing"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class RuntimeContext:
    job_id: str
    current_state: RuntimeState = RuntimeState.QUEUED
    current_worker: str = ""
    execution_time: float = 0.0
    retries: int = 0
    memory_context: Dict[str, Any] = field(default_factory=dict)
    strategy: Dict[str, Any] = field(default_factory=dict)
    assets: List[Dict[str, Any]] = field(default_factory=list)
    workers_finished: List[str] = field(default_factory=list)
    workers_remaining: List[str] = field(default_factory=list)
    current_errors: List[str] = field(default_factory=list)
    pipeline_modifiers: List[str] = field(default_factory=list)
    shared_objects: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)

class DynamicDAG:
    def __init__(self, initial_sequence: List[str]):
        self.sequence = initial_sequence.copy()
        
    def pop_next(self) -> Optional[str]:
        if self.sequence:
            return self.sequence.pop(0)
        return None
        
    def prepend(self, worker_name: str) -> None:
        self.sequence.insert(0, worker_name)
        
    def replace_remaining(self, new_sequence: List[str]) -> None:
        self.sequence = new_sequence.copy()

class RuntimeStateManager:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.states: Dict[str, RuntimeState] = {}
        
    def transition(self, context: RuntimeContext, new_state: RuntimeState) -> None:
        old_state = context.current_state
        self.bus.publish("StateExiting", {"job_id": context.job_id, "state": old_state.value})
        
        context.current_state = new_state
        self.states[context.job_id] = new_state
        
        self.bus.publish("StateEntered", {"job_id": context.job_id, "state": new_state.value})
        log.info("[%s] Transitioned to %s", context.job_id[:8], new_state.value)

class RuntimeExecutionEngine:
    def __init__(self, db, workers, event_bus: EventBus, config=None):
        self.db = db
        self.workers = workers
        self.bus = event_bus
        self.state_manager = RuntimeStateManager(self.bus)
        self.crash_manager = CrashManager(config, self.bus)
        
    def execute(self, job: Dict[str, Any], initial_sequence: List[str], checkpoint: Optional[Dict[str, Any]] = None) -> RuntimeContext:
        job_id = job.get("id", "unknown")
        
        # 6. Runtime Recovery
        if checkpoint:
            ctx = self._restore_checkpoint(checkpoint)
            dag = DynamicDAG(ctx.workers_remaining)
            log.info("[%s] Resuming from checkpoint at worker: %s", job_id[:8], ctx.current_worker)
        else:
            ctx = RuntimeContext(
                job_id=job_id,
                workers_remaining=initial_sequence.copy()
            )
            dag = DynamicDAG(initial_sequence)
        
        start_time = time.time()
        
        self.bus.publish("PipelineStarted", {"job_id": job_id})
        
        worker_failures = {} # Track global failures per worker to prevent infinite repair loops
        
        try:
            while True:
                current_worker_name = dag.pop_next()
                if not current_worker_name:
                    break
                    
                worker = self.workers.get(current_worker_name)
                if not worker:
                    log.warning("[%s] Worker %s not found, skipping", job_id[:8], current_worker_name)
                    ctx.workers_remaining = dag.sequence.copy()
                    continue
                    
                ctx.current_worker = current_worker_name
                self.state_manager.transition(ctx, self._map_worker_to_state(current_worker_name))
                
                # 4. Event Bus
                self.bus.publish("WorkerStarted", {"job_id": job_id, "worker": current_worker_name})
                
                w_start = time.time()
                success = False
                error_msg = ""
                
                # Start process tracking
                process = psutil.Process()
                cpu_before = process.cpu_percent()
                io_before = None
                try:
                    io_before = process.io_counters()
                except Exception:
                    pass
                
                # Save Checkpoint Before Execution
                ctx.workers_remaining = dag.sequence.copy()
                self._save_checkpoint(ctx)
                
                try:
                    # Actual execution
                    if hasattr(worker, "run"):
                        worker_state = ctx.shared_objects
                        worker_state["assets"] = ctx.assets
                        res = worker.run(job, worker_state)
                        ctx.assets = worker_state.get("assets", [])
                        success = res.status.name == "SUCCESS"
                        error_msg = res.reason if not success else ""
                    else:
                        success = True
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    
                w_duration = time.time() - w_start
                
                cpu_after = process.cpu_percent()
                ram_usage_mb = process.memory_info().rss / (1024 * 1024)
                disk_io = 0.0
                try:
                    io_after = process.io_counters()
                    if io_before and io_after:
                        disk_io = ((io_after.read_bytes - io_before.read_bytes) + (io_after.write_bytes - io_before.write_bytes)) / (1024 * 1024)
                except Exception:
                    pass
                    
                metrics = {"cpu": cpu_after, "ram": ram_usage_mb, "gpu": 0.0, "disk_io": disk_io, "network": 0.0}
                
                # 5. Runtime Metrics
                self._record_metrics(job_id, current_worker_name, w_duration, metrics, success)
                
                if success:
                    self.bus.publish("WorkerFinished", {"job_id": job_id, "worker": current_worker_name, "duration": w_duration})
                    ctx.workers_finished.append(current_worker_name)
                    ctx.retries = 0
                    
                    # Dynamic DAG modifications (Rules)
                    self._apply_dynamic_dag_rules(ctx, dag, current_worker_name, success)
                    ctx.workers_remaining = dag.sequence.copy()
                    
                else:
                    self.bus.publish("WorkerFailed", {"job_id": job_id, "worker": current_worker_name, "error": error_msg})
                    ctx.current_errors.append(error_msg)
                    
                    # Retry logic or Repair routing
                    if ctx.retries < 2:
                        ctx.retries += 1
                        log.info("[%s] Retrying %s (Attempt %d)", job_id[:8], current_worker_name, ctx.retries)
                        dag.prepend(current_worker_name) # Put it back to run next
                    else:
                        wf_count = worker_failures.get(current_worker_name, 0) + 1
                        worker_failures[current_worker_name] = wf_count
                        
                        if wf_count > 2:
                            log.error("[%s] Worker %s failed too many times despite repairs. Aborting.", job_id[:8], current_worker_name)
                            self.state_manager.transition(ctx, RuntimeState.FAILED)
                            self.bus.publish("PipelineCompleted", {"job_id": job_id, "success": False})
                            return ctx
                            
                        # Dynamic DAG modifications (Failure Rules)
                        repaired = self._apply_dynamic_dag_rules(ctx, dag, current_worker_name, success)
                        if not repaired:
                            self.state_manager.transition(ctx, RuntimeState.FAILED)
                            self.bus.publish("PipelineCompleted", {"job_id": job_id, "success": False})
                            return ctx
                            
                        ctx.retries = 0
                        ctx.workers_remaining = dag.sequence.copy()
                        
                ctx.execution_time = time.time() - start_time
            self.state_manager.transition(ctx, RuntimeState.COMPLETED)
            self.bus.publish("PipelineCompleted", {"job_id": job_id, "success": True})
            return ctx
            
        except Exception as e:
            self.crash_manager.handle_crash(ctx, dag, e)
            self.state_manager.transition(ctx, RuntimeState.FAILED)
            self.bus.publish("PipelineCompleted", {"job_id": job_id, "success": False})
            log.error("Pipeline crashed: %s", e)
            return ctx
        
    def _map_worker_to_state(self, worker_name: str) -> RuntimeState:
        m = {
            "internet": RuntimeState.SEARCHING_ASSETS,
            "analysis": RuntimeState.ANALYZING,
            "blender": RuntimeState.BLENDER_PROCESSING,
            "godot": RuntimeState.GODOT_IMPORT,
            "validation": RuntimeState.VALIDATION,
            "deploy": RuntimeState.PACKAGING,
            "improver": RuntimeState.REPAIRING,
            "code": RuntimeState.CODE_GENERATION
        }
        return m.get(worker_name, RuntimeState.PLANNING)
        
    def _record_metrics(self, job_id, worker, duration, metrics, success):
        self.db.add_worker_execution(
            job_id=job_id, worker_name=worker, execution_time=duration,
            cpu_usage=metrics["cpu"], ram_usage=metrics["ram"], gpu_usage=metrics["gpu"],
            success=success, retries=0, timeout=False, repair_triggered=False,
            tokens_used=100, assets_processed=0, failure_category=""
        )
        
    def _save_checkpoint(self, ctx: RuntimeContext):
        data = {
            "job_id": ctx.job_id,
            "workers_remaining": ctx.workers_remaining,
            "workers_finished": ctx.workers_finished,
            "current_worker": ctx.current_worker,
            "assets": ctx.assets
        }
        self.db.add_world_model_entry(ctx.job_id, "checkpoint", data)
        
    def _restore_checkpoint(self, data: Dict[str, Any]) -> RuntimeContext:
        ctx = RuntimeContext(job_id=data["job_id"])
        ctx.workers_remaining = data.get("workers_remaining", [])
        ctx.workers_finished = data.get("workers_finished", [])
        ctx.current_worker = data.get("current_worker", "")
        ctx.assets = data.get("assets", [])
        return ctx
        
    def _apply_dynamic_dag_rules(self, ctx: RuntimeContext, dag: DynamicDAG, current_worker: str, success: bool) -> bool:
        """Modifies DAG mid-execution based on rules. Returns True if handled, False if fatal."""
        if not success:
            if current_worker == "blender" and "improver" in self.workers:
                log.info("[%s] Blender failed. Injecting Project Improver.", ctx.job_id[:8])
                # We want to run improver, then try blender again
                dag.prepend(current_worker)
                dag.prepend("improver")
                return True
                
            if current_worker == "validation" and "godot" in self.workers:
                log.info("[%s] Validation failed. Returning to Godot.", ctx.job_id[:8])
                # We want to run godot, then validation again
                dag.prepend(current_worker)
                dag.prepend("godot")
                return True
                
            return False
            
        else:
            if current_worker == "analysis" and ctx.assets:
                # Example of skipping internet if analysis finds cached assets (not perfectly realistic but shows rule execution)
                pass
            return True
