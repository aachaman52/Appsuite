from __future__ import annotations
import threading
from typing import Any, Callable, Dict, List

class EventBus:
    """Thread-safe Pub-Sub Event Bus for decoupling Jarvis OS components."""
    
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {}
        self._lock = threading.RLock()
        
    def subscribe(self, event_type: str, callback: Callable[[str, Any], None]) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            
    def unsubscribe(self, event_type: str, callback: Callable[[str, Any], None]) -> None:
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass
                
    def publish(self, event_type: str, data: Any) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
            wildcard_callbacks = list(self._subscribers.get("*", []))
            
        for cb in callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass
        for cb in wildcard_callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass
