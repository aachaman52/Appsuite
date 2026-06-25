"""Message Bus for inter-agent communication."""
from __future__ import annotations

import queue
import threading
from typing import Any, Dict, List

class MessageBus:
    VALID_EVENTS = {
        "task_created", "task_started", "task_completed", "task_failed",
        "resource_warning", "replanning_required", "broadcast",
        "asset_status", "blender_status", "godot_status", "code_status"
    }

    def __init__(self):
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, topic: str) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(q)
        return q

    def unsubscribe(self, topic: str, q: queue.Queue):
        with self._lock:
            if topic in self._subscribers and q in self._subscribers[topic]:
                self._subscribers[topic].remove(q)

    def send(self, topic: str, message: Any):
        if topic not in self.VALID_EVENTS:
            import logging
            logging.warning(f"MessageBus: Unregistered topic used: {topic}")
            
        with self._lock:
            subs = self._subscribers.get(topic, []).copy()
        for q in subs:
            q.put(message)

    def broadcast(self, message: Any):
        """Broadcasts to all subscribed agents via the 'broadcast' topic."""
        self.send("broadcast", message)
