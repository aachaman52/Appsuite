"""Base framework for AppSuite Agents."""
from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List

from ..logging_setup import get_logger

log = get_logger("agents.base")

@dataclass
class AgentTask:
    task_id: str
    agent_type: str
    objective: str
    required_tools: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1
    expected_output: str = ""
    status: str = "PENDING"

@dataclass
class AgentResult:
    agent_name: str
    task: str
    status: str      # "success" | "failed"
    output: Any
    confidence: float
    execution_time: float


class BaseAgent(ABC):
    def __init__(self, name: str, message_bus=None, memory=None, orchestrator=None, providers=None):
        self.name = name
        self.message_bus = message_bus
        self.memory = memory
        self.orchestrator = orchestrator  # Can be GraphOrchestrator to run nodes
        self.providers = providers

    def receive_task(self, task: AgentTask):
        """Called when a task is first received."""
        pass

    @abstractmethod
    def plan(self, task: AgentTask) -> Any:
        """Create a plan or recommendation for the task."""
        pass

    @abstractmethod
    def execute_tools(self, plan: Any) -> Any:
        """Execute the planned tools/nodes."""
        raise NotImplementedError

    def write_memory(self, result: AgentResult):
        if self.memory and hasattr(self.memory, 'store_agent_strategy'):
            self.memory.store_agent_strategy(self.name, result)

    def run(self, task: AgentTask) -> AgentResult:
        """Main execution flow for the agent."""
        start_time = time.time()
        status = "failed"
        output = {}
        confidence = 0.0
        
        log.info("[%s] Started task: %s", self.name, task.objective)

        try:
            self.receive_task(task)
            if self.message_bus:
                self.message_bus.send("task_started", {"task_id": task.task_id, "agent": self.name})
            
            plan = self.plan(task)
            output = self.execute_tools(plan)
            status = "success"
            confidence = 1.0
            
            if self.message_bus:
                self.message_bus.send("task_completed", {"task_id": task.task_id, "agent": self.name, "status": "success"})
        except Exception as e:
            err = traceback.format_exc()
            log.error("[%s] Task failed: %s\n%s", self.name, str(e), err)
            output = {"error": str(e), "traceback": err}
            status = "failed"
            confidence = 0.0
            if self.message_bus:
                self.message_bus.send("task_failed", {"task_id": task.task_id, "agent": self.name, "error": str(e)})
            
        execution_time = time.time() - start_time
        result = AgentResult(
            agent_name=self.name,
            task=task.objective,
            status=status,
            output=output,
            confidence=confidence,
            execution_time=execution_time
        )
        
        self.write_memory(result)
        log.info("[%s] Finished task: %s (status=%s, time=%.2fs)", 
                 self.name, task.objective, status, execution_time)
        return result
