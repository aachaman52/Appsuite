from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from .event_bus import (
    EventBus, BaseEvent, TaskCreated, TaskStarted, TaskCompleted,
    TaskFailed, WorkerStarted, WorkerFinished, CheckpointSaved,
    RecoveryStarted, RecoveryCompleted, ResourceWarning, PipelineFinished
)
from ..logging_setup import get_logger

log = get_logger("engine.observability")

class ObservabilityWriter:
    def __init__(self, event_bus: EventBus, output_dir: Optional[Path] = None):
        self.event_bus = event_bus
        self.output_dir = output_dir or Path(".")
        self.events: List[Dict[str, Any]] = []
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.worker_runs: Dict[str, List[Dict[str, Any]]] = {}
        
        self.start_time = time.time()
        self.peak_ram = 0.0
        self.peak_cpu = 0.0
        self.retries = 0
        self.cache_hits = 0

        # Subscribe to all events
        self.event_bus.subscribe(TaskCreated, self.on_task_created)
        self.event_bus.subscribe(TaskStarted, self.on_task_started)
        self.event_bus.subscribe(TaskCompleted, self.on_task_completed)
        self.event_bus.subscribe(TaskFailed, self.on_task_failed)
        self.event_bus.subscribe(WorkerStarted, self.on_worker_started)
        self.event_bus.subscribe(WorkerFinished, self.on_worker_finished)
        self.event_bus.subscribe(CheckpointSaved, self.on_event)
        self.event_bus.subscribe(RecoveryStarted, self.on_event)
        self.event_bus.subscribe(RecoveryCompleted, self.on_event)
        self.event_bus.subscribe(ResourceWarning, self.on_resource_warning)
        self.event_bus.subscribe(PipelineFinished, self.on_pipeline_finished)

    def on_event(self, event: BaseEvent):
        self.events.append({
            "event": type(event).__name__,
            "timestamp": event.timestamp,
            "data": {k: v for k, v in event.__dict__.items() if k != "timestamp"}
        })

    def on_task_created(self, event: TaskCreated):
        self.on_event(event)
        self.tasks[event.task_id] = {
            "task_id": event.task_id,
            "agent_type": event.agent_type,
            "priority": event.priority,
            "dependencies": [],
            "status": "pending",
            "start_time": None,
            "end_time": None,
            "duration": 0.0,
            "error": None
        }

    def on_task_started(self, event: TaskStarted):
        self.on_event(event)
        if event.task_id in self.tasks:
            self.tasks[event.task_id]["status"] = "running"
            self.tasks[event.task_id]["start_time"] = event.timestamp

    def on_task_completed(self, event: TaskCompleted):
        self.on_event(event)
        if event.task_id in self.tasks:
            self.tasks[event.task_id]["status"] = "success"
            self.tasks[event.task_id]["end_time"] = event.timestamp
            self.tasks[event.task_id]["duration"] = event.duration

    def on_task_failed(self, event: TaskFailed):
        self.on_event(event)
        if event.task_id in self.tasks:
            self.tasks[event.task_id]["status"] = "failed"
            self.tasks[event.task_id]["end_time"] = event.timestamp
            self.tasks[event.task_id]["error"] = event.error
        self.retries += 1

    def on_worker_started(self, event: WorkerStarted):
        self.on_event(event)
        if event.worker_name not in self.worker_runs:
            self.worker_runs[event.worker_name] = []
        self.worker_runs[event.worker_name].append({
            "task_id": event.task_id,
            "start_time": event.timestamp,
            "end_time": None,
            "duration": 0.0,
            "status": "running"
        })

    def on_worker_finished(self, event: WorkerFinished):
        self.on_event(event)
        if event.worker_name in self.worker_runs and self.worker_runs[event.worker_name]:
            # Find the running one for this task
            for run in reversed(self.worker_runs[event.worker_name]):
                if run["task_id"] == event.task_id and run["end_time"] is None:
                    run["end_time"] = event.timestamp
                    run["duration"] = event.duration
                    run["status"] = "success"
                    break

    def on_resource_warning(self, event: ResourceWarning):
        self.on_event(event)
        if event.resource == "ram":
            self.peak_ram = max(self.peak_ram, event.level)
        elif event.resource == "cpu":
            self.peak_cpu = max(self.peak_cpu, event.level)

    def on_pipeline_finished(self, event: PipelineFinished):
        self.on_event(event)
        self.write_outputs()

    def update_resource_peaks(self, ram: float, cpu: float):
        self.peak_ram = max(self.peak_ram, ram)
        self.peak_cpu = max(self.peak_cpu, cpu)

    def register_cache_hit(self):
        self.cache_hits += 1

    def write_outputs(self):
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # 1. execution_metrics.json
        total_dur = time.time() - self.start_time
        successes = sum(1 for t in self.tasks.values() if t["status"] == "success")
        failures = sum(1 for t in self.tasks.values() if t["status"] == "failed")
        metrics = {
            "total_duration": total_dur,
            "task_count": len(self.tasks),
            "success_count": successes,
            "failure_count": failures,
            "ram_usage_peak": self.peak_ram,
            "cpu_usage_peak": self.peak_cpu,
            "cache_hits": self.cache_hits,
            "worker_retries": self.retries
        }
        with open(self.output_dir / "execution_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        # 2. execution_timeline.json
        with open(self.output_dir / "execution_timeline.json", "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)

        # 3. dependency_graph.json
        dep_graph = {
            "tasks": self.tasks,
            "adjacency_list": {t_id: t["dependencies"] for t_id, t in self.tasks.items()}
        }
        with open(self.output_dir / "dependency_graph.json", "w", encoding="utf-8") as f:
            json.dump(dep_graph, f, indent=2)

        # 4. worker_statistics.json
        worker_stats = {}
        for worker, runs in self.worker_runs.items():
            completed_runs = [r for r in runs if r["end_time"] is not None]
            total_runs = len(runs)
            success_runs = sum(1 for r in runs if r["status"] == "success")
            avg_dur = sum(r["duration"] for r in completed_runs) / len(completed_runs) if completed_runs else 0.0
            worker_stats[worker] = {
                "total_runs": total_runs,
                "success_runs": success_runs,
                "failure_runs": total_runs - success_runs,
                "avg_duration": avg_dur,
                "total_duration": sum(r["duration"] for r in completed_runs)
            }
        with open(self.output_dir / "worker_statistics.json", "w", encoding="utf-8") as f:
            json.dump(worker_stats, f, indent=2)
            
        log.info(f"Observability files written to {self.output_dir}")
