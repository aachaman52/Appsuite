from __future__ import annotations
from typing import Any, Dict, List

class AgentMemory:
    def __init__(self):
        self.agent_history = []

    def store_agent_strategy(self, agent_name: str, result: Any) -> None:
        if hasattr(result, '__dict__'):
            data = result.__dict__
        else:
            data = result
            
        self.agent_history.append({
            "agent_name": agent_name,
            "data": data
        })

    def recall_agent_strategy(self, agent_name: str) -> List[Dict[str, Any]]:
        return [h["data"] for h in self.agent_history if h["agent_name"] == agent_name]
