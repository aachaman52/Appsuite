"""Base framework for AppSuite Agents."""
from __future__ import annotations

import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Union

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
    estimated_duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"

@dataclass
class AgentPlan:
    task_id: str
    objective: str
    subtasks: List[str] = field(default_factory=list)
    priorities: Dict[str, int] = field(default_factory=dict)
    conditions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ReflectionResult:
    success: bool
    gaps: List[str] = field(default_factory=list)
    repair_actions: List[str] = field(default_factory=list)

@dataclass
class AgentResult:
    agent_name: str
    task: str
    status: str      # "success" | "failed"
    output: Any
    confidence: float
    execution_time: float


class BaseAgent(ABC):
    def __init__(self, name: str, message_bus=None, memory=None, orchestrator=None, providers=None, workers=None, event_bus=None):
        self.name = name
        self.message_bus = message_bus
        self.memory = memory
        self.orchestrator = orchestrator  # Can be GraphOrchestrator to run nodes
        self.providers = providers
        self.workers = workers or {}
        self.event_bus = event_bus

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
            agent_plan = self._normalize_plan(task, plan)
            output = self.execute_tools(self._unpack_plan(agent_plan))
            status = "success"
            confidence = 1.0

            reflection = self.reflect(task, AgentResult(self.name, task.objective, status, output, confidence, 0.0))
            if not reflection.success:
                attempts = 0
                while attempts < 2 and not reflection.success:
                    attempts += 1
                    repair_plan = self.repair(task, reflection)
                    if not repair_plan:
                        break
                    agent_plan = self._normalize_plan(task, repair_plan)
                    output = self.execute_tools(self._unpack_plan(agent_plan))
                    status = "success"
                    confidence = 1.0
                    reflection = self.reflect(task, AgentResult(self.name, task.objective, status, output, confidence, 0.0))
                    if reflection.success:
                        break
            
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

    def _normalize_plan(self, task: AgentTask, plan: Any) -> AgentPlan:
        if isinstance(plan, AgentPlan):
            return plan
        if isinstance(plan, list):
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=plan)
        if isinstance(plan, str):
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=[plan])
        if isinstance(plan, dict):
            return AgentPlan(task_id=task.task_id, objective=task.objective, metadata=plan)
        return AgentPlan(task_id=task.task_id, objective=task.objective)

    def _unpack_plan(self, plan: AgentPlan) -> Any:
        if plan.subtasks:
            return plan.subtasks
        if plan.metadata:
            return plan.metadata
        return []

    def reflect(self, task: AgentTask, result: AgentResult) -> ReflectionResult:
        success = result.status == "success"
        gaps = []
        if not success:
            gaps.append("Agent execution did not complete successfully.")
        return ReflectionResult(success=success, gaps=gaps, repair_actions=["retry" ] if not success else [])

    def repair(self, task: AgentTask, reflection: ReflectionResult) -> Optional[AgentPlan]:
        if reflection.repair_actions:
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["retry"])
        return None
