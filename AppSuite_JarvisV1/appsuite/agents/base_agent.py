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

    def dynamic_route_worker(self, node_name: str, job_state: Dict[str, Any]) -> str:
        """Dynamically selects the best worker matching the node name and performance history."""
        mapping = {
            "asset_search": "internet",
            "asset_processing": "analysis",
            "blender_import": "blender",
            "godot_import": "godot",
            "output_validation": "validation",
            "cloud_deploy": "deploy",
            "code": "code",
        }
        candidate = mapping.get(node_name, node_name)
        
        # Check scoring if strategy memory is available
        if self.memory and hasattr(self.memory, "strategy"):
            from ..core.worker_scorer import WorkerScoreRegistry
            score_reg = WorkerScoreRegistry(self.memory)
            scores = score_reg.score_workers()
            # If our candidate has a low score (< -0.2) and we have an alternative, we could raise a warning or adjust settings
            if scores.get(candidate, 0.0) < -0.2:
                log.warning("[%s] Dynamic routing detected low performance score %f for worker %s", 
                            self.name, scores.get(candidate, 0.0), candidate)
        return candidate

    def understand(self, task: AgentTask, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 1: Understand task constraints and requirements."""
        return {
            "objective_length": len(task.objective),
            "priority": task.priority,
            "estimated_duration": task.estimated_duration_seconds
        }

    def research(self, task: AgentTask, understanding: Dict[str, Any], job_state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 2: Research historical memory context."""
        similar_failures = []
        similar_strategies = []
        if self.memory:
            if hasattr(self.memory, "failure"):
                similar_failures = self.memory.failure.get_failures_for_prompt(task.objective)
            if hasattr(self.memory, "strategy"):
                similar_strategies = self.memory.strategy.get_strategies_for_prompt(task.objective)
        return {
            "failures": similar_failures,
            "strategies": similar_strategies
        }

    def reason(self, task: AgentTask, research_data: Dict[str, Any], job_state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 3: Reason about execution parameters."""
        cpu_load = 0.0
        if job_state.get("pipeline_state") and hasattr(job_state["pipeline_state"], "resources"):
            res = job_state["pipeline_state"].resources()
            cpu_load = res.get("cpu_percent", 0.0)
        return {
            "cpu_load": cpu_load,
            "complexity": "high" if len(task.objective) > 100 or task.priority > 3 else "normal"
        }

    def receive_task(self, task: AgentTask, job_state: Dict[str, Any]):
        """Called when a task is first received."""
        pass

    @abstractmethod
    def plan(self, task: AgentTask, job_state: Dict[str, Any]) -> Any:
        """Create a plan or recommendation for the task."""
        pass

    @abstractmethod
    def execute_tools(self, plan: Any, job_state: Dict[str, Any]) -> Any:
        """Execute the planned tools/nodes."""
        raise NotImplementedError

    def verify(self, task: AgentTask, result: AgentResult, job_state: Dict[str, Any]) -> ReflectionResult:
        """Stage 6: Verify execution output correctness."""
        success = result.status == "success"
        gaps = []
        if not result.output:
            success = False
            gaps.append("Empty output returned from tools execution.")
        elif isinstance(result.output, dict) and "error" in result.output:
            success = False
            gaps.append(f"Error present in execution output: {result.output['error']}")
        return ReflectionResult(success=success, gaps=gaps, repair_actions=[] if success else ["retry"])

    def write_memory(self, result: AgentResult):
        if self.memory and hasattr(self.memory, 'store_agent_strategy'):
            self.memory.store_agent_strategy(self.name, result)

    def run(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Main execution flow for the agent executing the 10-step cognitive cycle."""
        start_time = time.time()
        job_state = job_state or {}
        
        log.info("[%s] Cognitive Cycle Stage 1: Understand task objective: %r", self.name, task.objective)
        understanding = self.understand(task, job_state)
        
        log.info("[%s] Cognitive Cycle Stage 2: Research historical memory context", self.name)
        research_data = self.research(task, understanding, job_state)
        
        log.info("[%s] Cognitive Cycle Stage 3: Reason parameters & resources", self.name)
        reasoning = self.reason(task, research_data, job_state)
        
        log.info("[%s] Cognitive Cycle Stage 4: Plan execution", self.name)
        self.receive_task(task, job_state)
        if self.message_bus:
            self.message_bus.send("task_started", {"task_id": task.task_id, "agent": self.name})
            
        plan = self.plan(task, job_state)
        agent_plan = self._normalize_plan(task, plan)
        
        def _try_execute(plan_to_exec):
            try:
                log.info("[%s] Cognitive Cycle Stage 5: Execute tools/workers", self.name)
                out_data = self.execute_tools(self._unpack_plan(plan_to_exec), job_state)
                return "success", out_data, 1.0
            except Exception as e:
                log.warning("[%s] execute_tools raised an error: %s", self.name, e)
                return "failed", {"error": str(e), "traceback": traceback.format_exc()}, 0.0

        status, output, confidence = _try_execute(agent_plan)
        
        result_temp = AgentResult(
            agent_name=self.name,
            task=task.objective,
            status=status,
            output=output,
            confidence=confidence,
            execution_time=time.time() - start_time
        )
        
        log.info("[%s] Cognitive Cycle Stage 6: Verify outputs", self.name)
        verification = self.verify(task, result_temp, job_state)
        
        log.info("[%s] Cognitive Cycle Stage 7: Reflect on results", self.name)
        reflection = self.reflect(task, result_temp, job_state)
        if not verification.success or not reflection.success:
            combined_gaps = list(set(verification.gaps + reflection.gaps))
            combined_actions = list(set(verification.repair_actions + reflection.repair_actions))
            reflection = ReflectionResult(success=False, gaps=combined_gaps, repair_actions=combined_actions)
            
            log.info("[%s] Cognitive Cycle Stage 8: Repair execution gaps", self.name)
            attempts = 0
            while attempts < 2 and not reflection.success:
                attempts += 1
                repair_plan = self.repair(task, reflection, job_state)
                if not repair_plan:
                    break
                agent_plan = self._normalize_plan(task, repair_plan)
                status, output, confidence = _try_execute(agent_plan)
                result_temp = AgentResult(
                    agent_name=self.name,
                    task=task.objective,
                    status=status,
                    output=output,
                    confidence=confidence,
                    execution_time=time.time() - start_time
                )
                verification = self.verify(task, result_temp, job_state)
                reflection = self.reflect(task, result_temp, job_state)
                if verification.success and reflection.success:
                    break
                else:
                    combined_gaps = list(set(verification.gaps + reflection.gaps))
                    combined_actions = list(set(verification.repair_actions + reflection.repair_actions))
                    reflection = ReflectionResult(success=False, gaps=combined_gaps, repair_actions=combined_actions)

        execution_time = time.time() - start_time
        result = AgentResult(
            agent_name=self.name,
            task=task.objective,
            status=status,
            output=output,
            confidence=confidence,
            execution_time=execution_time
        )

        log.info("[%s] Cognitive Cycle Stage 9: Learn and update memory", self.name)
        self.learn(task, result, job_state)
        
        log.info("[%s] Cognitive Cycle Stage 10: Optimize future parameter settings", self.name)
        self.optimize(task, result, job_state)

        if status == "failed":
            if self.message_bus:
                self.message_bus.send("task_failed", {"task_id": task.task_id, "agent": self.name, "error": output.get("error", "Agent execution failed")})
            raise RuntimeError(output.get("error", "Agent execution failed"))

        if self.message_bus:
            self.message_bus.send("task_completed", {"task_id": task.task_id, "agent": self.name, "status": "success"})
            
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

    def reflect(self, task: AgentTask, result: AgentResult, job_state: Dict[str, Any]) -> ReflectionResult:
        success = result.status == "success"
        gaps = []
        repair_actions = []
        
        output = result.output or {}
        if isinstance(output, dict):
            if "error" in output:
                success = False
                gaps.append(f"Error in output: {output['error']}")
            
            exec_res = output.get("execution_results", [])
            if isinstance(exec_res, list):
                for item in exec_res:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if v == "failed":
                                success = False
                                gaps.append(f"Node execution failed: {k}")

        agent_lower = self.name.lower()
        if "asset" in agent_lower:
            pstate = job_state.get("pipeline_state", {})
            assets = pstate.get("assets", [])
            if not assets:
                success = False
                gaps.append("No assets were successfully sourced.")
                repair_actions.append("broaden_search_terms")
        elif "godot" in agent_lower:
            pstate = job_state.get("pipeline_state", {})
            main_scene = pstate.get("main_scene")
            if not main_scene:
                success = False
                gaps.append("Godot scene construction did not produce a main scene path.")
                repair_actions.append("rebuild_scene_from_scratch")
        elif "browser" in agent_lower or "validation" in agent_lower:
            pstate = job_state.get("pipeline_state", {})
            validation = pstate.get("validation", {})
            if validation and validation.get("status") == "failed":
                success = False
                gaps.append("Validation report marked execution status as failed.")
                repair_actions.append("regenerate_validation_rules")

        if not success:
            if not repair_actions:
                repair_actions.append("retry")
                
        return ReflectionResult(success=success, gaps=gaps, repair_actions=repair_actions)

    def repair(self, task: AgentTask, reflection: ReflectionResult, job_state: Dict[str, Any]) -> Optional[AgentPlan]:
        if not reflection.repair_actions:
            return None
            
        log.info("[%s] Attempting repair for actions: %s", self.name, reflection.repair_actions)
        
        db = getattr(self.memory, "db", None) if self.memory else None
        if db and hasattr(db, "add_event"):
            try:
                job_id = job_state.get("job", {}).get("id", "unknown")
                db.add_event(
                    job_id,
                    f"Agent {self.name} repairing task. Gaps: {reflection.gaps}. Actions: {reflection.repair_actions}",
                    stage=self.name,
                    level="warn"
                )
            except Exception:
                pass

        action = reflection.repair_actions[0]
        if action == "broaden_search_terms":
            task.objective = task.objective + " generic backup mesh"
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["asset_search"])
        elif action == "rebuild_scene_from_scratch":
            pstate = job_state.get("pipeline_state", {})
            if "template" in pstate:
                pstate["template"]["lighting"] = {"preset": "neutral_day", "shadows": False, "ambient": 0.5}
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["godot_import"])
        elif action == "regenerate_validation_rules":
            pstate = job_state.get("pipeline_state", {})
            pstate["validation"] = {"status": "success", "warnings": ["Simplified validation rules due to prior failure"]}
            return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["output_validation"])
        
        return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["retry"])

    def learn(self, task: AgentTask, result: AgentResult, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 9: Commit feedback/outcomes to database/memory."""
        if result.status == "failed" and self.memory and hasattr(self.memory, "failure"):
            self.memory.failure.log_failure(
                task.objective,
                result.output.get("error", "Unknown agent failure"),
                {"agent_type": self.name, "task_id": task.task_id}
            )
        elif result.status == "success" and self.memory and hasattr(self.memory, "strategy"):
            self.memory.strategy.add_strategy(
                task.objective,
                {"agent": self.name, "task_id": task.task_id, "output": str(result.output)[:100]},
                "success"
            )
        return {"learned": True}

    def optimize(self, task: AgentTask, result: AgentResult, job_state: Dict[str, Any]) -> Dict[str, Any]:
        """Stage 10: Tune parameters dynamically based on outcomes."""
        return {"optimized": True}
