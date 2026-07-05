from __future__ import annotations
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from pathlib import Path

from .base_agent import AgentResult, BaseAgent, AgentTask
from .asset_agent import AssetAgent
from .blender_agent import BlenderAgent
from .godot_agent import GodotAgent
from .code_agent import CodeAgent
from .browser_agent import BrowserAgent
from .message_bus import MessageBus
from ..logging_setup import get_logger

log = get_logger("agents.coordinator")

class AgentCoordinator:
    """Manages the parallel execution of multiple specialized agents."""

    def __init__(self, message_bus: MessageBus, memory=None, orchestrator=None, hardware=None, brain=None, workers=None):
        self.message_bus = message_bus
        self.memory = memory
        self.orchestrator = orchestrator
        self.hardware = hardware
        self.brain = brain
        self.workers = workers or {}
        
        # event_bus can be retrieved from orchestrator
        event_bus_instance = getattr(orchestrator, "event_bus", None)
        
        providers_instance = getattr(brain, "providers", getattr(brain, "provider_manager", None)) if brain else None
        self.agent_registry = {
            "AssetAgent": AssetAgent("AssetAgent", message_bus, memory, orchestrator, providers=providers_instance, workers=self.workers, event_bus=event_bus_instance),
            "BlenderAgent": BlenderAgent("BlenderAgent", message_bus, memory, orchestrator, providers=providers_instance, workers=self.workers, event_bus=event_bus_instance),
            "GodotAgent": GodotAgent("GodotAgent", message_bus, memory, orchestrator, providers=providers_instance, workers=self.workers, event_bus=event_bus_instance),
            "CodeAgent": CodeAgent("CodeAgent", message_bus, memory, orchestrator, providers=providers_instance, workers=self.workers, event_bus=event_bus_instance),
            "BrowserAgent": BrowserAgent("BrowserAgent", message_bus, memory, orchestrator, providers=providers_instance, workers=self.workers, event_bus=event_bus_instance),
        }
        for agent in self.agent_registry.values():
            setattr(agent, "coordinator", self)
        
        # Start timeline logger
        self.timeline_events = []
        self._timeline_thread = threading.Thread(target=self._log_timeline, daemon=True)
        self._timeline_thread.start()

    def _log_timeline(self):
        q = self.message_bus.subscribe("broadcast") # We actually need all topics, but MessageBus doesn't support wildcard yet. 
        # Actually, let's subscribe to valid topics directly
        topics = [
            "task_created", "task_started", "task_completed", "task_failed",
            "resource_warning", "replanning_required"
        ]
        queues = {t: self.message_bus.subscribe(t) for t in topics}
        
        import time
        from ..config import PROJECT_ROOT
        # It's a daemon thread, it will just poll
        while True:
            for t, q in queues.items():
                import queue
                try:
                    msg = q.get_nowait()
                    self.timeline_events.append({
                        "time": time.time(),
                        "event": t,
                        "data": msg
                    })
                    # Write to file
                    timeline_path = Path("agent_timeline.json")
                    try:
                        with open(timeline_path, "w") as f:
                            json.dump(self.timeline_events, f, indent=2)
                    except Exception:
                        pass
                except queue.Empty:
                    pass
            time.sleep(0.1)

    def execute_plan(self, agent_tasks: List[AgentTask], job_state: Dict[str, Any]) -> List[AgentResult]:
        """
        Executes a DAG of AgentTasks by delegating to the GraphOrchestrator.
        """
        if self.orchestrator:
            log.info("AgentCoordinator delegating DAG to GraphOrchestrator.")
            # Register agents into orchestrator if they aren't already
            for agent_name, agent in self.agent_registry.items():
                if agent_name not in self.orchestrator.nodes:
                    self.orchestrator.add_node(agent_name, agent)
                    
            try:
                results = self.orchestrator.run_dag(agent_tasks, job_state, self.hardware)
                return results
            except RuntimeError as e:
                if hasattr(e, "results") and any(r.status == "failed" for r in e.results):
                    err_str = str(e)
                    if "TASK_TIMEOUT" in err_str or "Deadlock" in err_str or "Health check" in err_str:
                        raise
                    return e.results
                raise
        else:
            log.warning("No GraphOrchestrator provided. Falling back to empty execution.")
            return []

    def delegate(self, from_agent: str, to_agent_type: str, objective: str, timeout: float = 10.0) -> Any:
        if not self.message_bus:
            raise RuntimeError("MessageBus is not configured for delegation")
        topic = f"delegate.{to_agent_type}"
        request = {
            "from_agent": from_agent,
            "objective": objective
        }
        try:
            return self.message_bus.request(topic, request, timeout=timeout)
        except Exception as exc:
            log.warning("Agent delegation to %s timed out: %s", to_agent_type, exc)
            return None


