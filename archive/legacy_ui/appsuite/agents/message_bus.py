import queue
import threading
import uuid
from typing import Dict, List, Any

class MessageBus:
    """Thread-safe Pub-Sub Message Bus for agents."""
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

    def send(self, topic: str, message: Any) -> None:
        with self._lock:
            # Send to specific topic subscribers
            if topic in self._subscribers:
                for q in self._subscribers[topic]:
                    q.put(message)
            # Send to broadcast topic subscribers if any
            if topic != "broadcast" and "broadcast" in self._subscribers:
                for q in self._subscribers["broadcast"]:
                    q.put({"topic": topic, "message": message})

    def unsubscribe(self, topic: str, queue_obj: queue.Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(topic)
            if not subscribers:
                return
            if queue_obj in subscribers:
                subscribers.remove(queue_obj)
            if not subscribers:
                self._subscribers.pop(topic, None)

    def request(self, topic: str, message: Any, timeout: float = 10.0) -> Any:
        reply_topic = f"__response__{uuid.uuid4().hex}"
        q = self.subscribe(reply_topic)
        request_payload = {
            "payload": message,
            "reply_to": reply_topic
        }
        self.send(topic, request_payload)
        try:
            return q.get(timeout=timeout)
        finally:
            self.unsubscribe(reply_topic, q)

    def respond(self, reply_to: str, message: Any) -> None:
        self.send(reply_to, message)
