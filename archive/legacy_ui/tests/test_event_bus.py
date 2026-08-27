from __future__ import annotations
from appsuite.core.event_bus import EventBus

def test_event_bus_basic():
    bus = EventBus()
    received = []
    
    def cb(event_type, data):
        received.append((event_type, data))
        
    bus.subscribe("test_event", cb)
    bus.publish("test_event", {"payload": "hello"})
    
    assert len(received) == 1
    assert received[0] == ("test_event", {"payload": "hello"})
    
    # Test unsubscribe
    bus.unsubscribe("test_event", cb)
    bus.publish("test_event", {"payload": "ignored"})
    assert len(received) == 1

def test_event_bus_wildcard():
    bus = EventBus()
    received = []
    
    def wildcard_cb(event_type, data):
        received.append((event_type, data))
        
    bus.subscribe("*", wildcard_cb)
    bus.publish("event_one", 1)
    bus.publish("event_two", 2)
    
    assert len(received) == 2
    assert received[0] == ("event_one", 1)
    assert received[1] == ("event_two", 2)
