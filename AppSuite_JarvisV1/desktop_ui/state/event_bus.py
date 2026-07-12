class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.listeners = {}
        return cls._instance

    def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def publish(self, event_type: str, data: dict) -> None:
        if event_type in self.listeners:
            for cb in self.listeners[event_type]:
                try:
                    cb(data)
                except Exception as e:
                    print(f"[EventBus] Error in callback for {event_type}: {e}")

event_bus = EventBus()
