"""CodeAgent — generates GDScript/C# gameplay scripts via the CodeWorker.

Thread safety note
------------------
``execute_tools`` receives ``job_state`` as an explicit parameter rather than
reading it from ``self.current_job_state``.  This means the same agent instance
can be called concurrently from multiple ``ThreadPoolExecutor`` threads without
any shared mutable state between invocations.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, AgentTask
from ..config import load_config
from ..logging_setup import get_logger

log = get_logger("agents.code")


class CodeAgent(BaseAgent):
    """Agent responsible for generating gameplay scripts via the code worker."""

    def receive_task(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> None:
        log.info("[%s] Creating scripts for: %s", self.name, task.objective)
        if self.message_bus:
            self.message_bus.send("code_status", "Creating gameplay scripts...")

    def plan(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> List[str]:
        """Return the ordered pipeline nodes this agent will execute."""
        return ["code"]

    def execute_tools(self, plan: Any, job_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute code generation using the isolated ``job_state`` passed in.

        Parameters
        ----------
        plan      : Ordered list of steps (currently just ``["code"]``).
        job_state : Isolated per-invocation state ``{"job": ..., "pipeline_state": ...}``.
                    Must NOT be stored on ``self`` — each thread call receives its own copy.
        """
        if self.message_bus:
            self.message_bus.send("code_status", "Executing code worker...")

        exec_results: List[Dict[str, Any]] = []
        script_path = ""
        lines = 0

        if not job_state:
            log.warning("[%s] execute_tools called with no job_state — skipping execution", self.name)
            return {"execution_results": exec_results, "lines": lines, "script_path": script_path}

        job = job_state["job"]
        pstate = job_state["pipeline_state"]

        worker = self.workers.get("code")
        if worker:
            res = worker.process(job, pstate)
            status_val = res.status.value
            exec_results.append({"code_generation": status_val})
            if status_val == "failed":
                if "Health check failed" in res.reason:
                    raise RuntimeError(f"Health check failed for code: {res.reason}")
                raise RuntimeError(f"code_generation failed: {res.reason}")

            script_path = res.data.get("script_path", "")
            if script_path and Path(script_path).exists():
                lines = len(Path(script_path).read_text(encoding="utf-8").splitlines())

        return {"execution_results": exec_results, "lines": lines, "script_path": script_path}
