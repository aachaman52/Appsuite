from __future__ import annotations
from typing import Any, Dict, List, Optional
from ...db import Database

from .worker_memory import WorkerMemory
from .agent_memory import AgentMemory
from .failure_memory import FailureMemory
from .strategy_memory import StrategyMemory

class SemanticMemory:
    """Unified Semantic Memory System Facade."""
    def __init__(self, db: Database):
        self.worker = WorkerMemory(db)
        self.agent = AgentMemory()
        self.failure = FailureMemory(db)
        self.strategy = StrategyMemory(db)

    # Delegate existing interface to maintain backward compatibility
    def remember(self, *args, **kwargs):
        return self.worker.remember(*args, **kwargs)

    def recall(self, *args, **kwargs):
        return self.worker.recall(*args, **kwargs)

    def recall_similar(self, *args, **kwargs):
        return self.worker.recall_similar(*args, **kwargs)

    def store_agent_strategy(self, *args, **kwargs):
        return self.agent.store_agent_strategy(*args, **kwargs)

    def recall_agent_strategy(self, *args, **kwargs):
        return self.agent.recall_agent_strategy(*args, **kwargs)
