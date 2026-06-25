from __future__ import annotations

class StrategyMemory:
    """Stores high-level planning strategies from JarvisBrain."""
    def __init__(self):
        self.strategies = []

    def add_strategy(self, strategy: dict):
        self.strategies.append(strategy)
