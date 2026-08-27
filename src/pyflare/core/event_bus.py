"""Thread-safe Unified Pub-Sub Event Bus for PyFlare components and engine events."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type, Union

log = logging.getLogger("pyflare.event_bus")


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
    """Unified Thread-safe Pub-Sub Event Bus supporting both string-topic and typed events."""

    def __init__(self) -> None:
        self._topic_subscribers: Dict[str, List[Callable]] = {}
        self._typed_handlers: Dict[Type[BaseEvent], List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_type: Union[str, Type[BaseEvent]], handler: Callable) -> None:
        with self._lock:
            if isinstance(event_type, str):
                if event_type not in self._topic_subscribers:
                    self._topic_subscribers[event_type] = []
                self._topic_subscribers[event_type].append(handler)
            else:
                if event_type not in self._typed_handlers:
                    self._typed_handlers[event_type] = []
                self._typed_handlers[event_type].append(handler)

    def unsubscribe(self, event_type: Union[str, Type[BaseEvent]], handler: Callable) -> None:
        with self._lock:
            if isinstance(event_type, str):
                if event_type in self._topic_subscribers:
                    try:
                        self._topic_subscribers[event_type].remove(handler)
                    except ValueError:
                        pass
            else:
                if event_type in self._typed_handlers:
                    try:
                        self._typed_handlers[event_type].remove(handler)
                    except ValueError:
                        pass

    def publish(self, event_or_type: Union[str, BaseEvent], data: Any = None) -> None:
        with self._lock:
            if isinstance(event_or_type, str):
                topic = event_or_type
                callbacks = list(self._topic_subscribers.get(topic, []))
                wildcard_callbacks = list(self._topic_subscribers.get("*", []))
                
                for cb in callbacks:
                    try:
                        cb(topic, data)
                    except Exception as e:
                        log.warning(f"Error in subscriber for topic '{topic}': {e}")
                        
                for cb in wildcard_callbacks:
                    try:
                        cb(topic, data)
                    except Exception as e:
                        log.warning(f"Error in wildcard subscriber for topic '{topic}': {e}")
            else:
                # Typed BaseEvent
                event = event_or_type
                event_cls = type(event)
                typed_cbs = list(self._typed_handlers.get(event_cls, []))
                for handler in typed_cbs:
                    try:
                        handler(event)
                    except Exception as e:
                        log.warning(f"Error in typed event handler {event_cls.__name__}: {e}")
                
                # Also notify string topic subscribers using class name
                topic = event_cls.__name__
                callbacks = list(self._topic_subscribers.get(topic, []))
                wildcard_callbacks = list(self._topic_subscribers.get("*", []))
                for cb in callbacks:
                    try:
                        cb(topic, event)
                    except Exception:
                        pass
                for cb in wildcard_callbacks:
                    try:
                        cb(topic, event)
                    except Exception:
                        pass
