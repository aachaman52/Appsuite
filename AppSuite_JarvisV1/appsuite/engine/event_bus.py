from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type

@dataclass
class BaseEvent:
    timestamp: float = field(default_factory=time.time)
    job_id: str = ""

@dataclass
class TaskCreated(BaseEvent):
    task_id: str = ""
    agent_type: str = ""
    priority: int = 1

@dataclass
class TaskStarted(BaseEvent):
    task_id: str = ""
    agent_name: str = ""

@dataclass
class TaskCompleted(BaseEvent):
    task_id: str = ""
    duration: float = 0.0
    status: str = ""

@dataclass
class TaskFailed(BaseEvent):
    task_id: str = ""
    error: str = ""
    traceback: str = ""

@dataclass
class WorkerStarted(BaseEvent):
    worker_name: str = ""
    task_id: str = ""

@dataclass
class WorkerFinished(BaseEvent):
    worker_name: str = ""
    task_id: str = ""
    duration: float = 0.0

@dataclass
class CheckpointSaved(BaseEvent):
    node_count: int = 0
    path: str = ""

@dataclass
class RecoveryStarted(BaseEvent):
    resumed_from: str = ""
    skipped_tasks: List[str] = field(default_factory=list)

@dataclass
class RecoveryCompleted(BaseEvent):
    recovered_tasks: int = 0

@dataclass
class ResourceWarning(BaseEvent):
    resource: str = ""
    level: float = 0.0
    threshold: float = 90.0

@dataclass
class PipelineFinished(BaseEvent):
    total_tasks: int = 0
    succeeded: int = 0
    failed: int = 0
    duration: float = 0.0

class EventBus:
    def __init__(self):
        self._handlers: Dict[Type[BaseEvent], List[Callable[[BaseEvent], None]]] = {}

    def subscribe(self, event_type: Type[BaseEvent], handler: Callable[[Any], None]):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[BaseEvent], handler: Callable[[Any], None]):
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    def publish(self, event: BaseEvent):
        event_type = type(event)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    import logging
                    logging.warning(f"Error handling event {event_type.__name__}: {e}")
