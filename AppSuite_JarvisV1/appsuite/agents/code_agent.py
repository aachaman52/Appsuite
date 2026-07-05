from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict
from .base_agent import BaseAgent, AgentTask
from ..config import load_config

class CodeAgent(BaseAgent):
    def receive_task(self, task: AgentTask):
        print(f"[{self.name}] Creating scripts")
        if self.message_bus:
            self.message_bus.send("code_status", "Creating gameplay scripts...")

    def plan(self, task: AgentTask) -> Any:
        return ["code"]

    def execute_tools(self, plan: Any) -> Any:
        if self.message_bus:
            self.message_bus.send("code_status", "Executing code worker...")
            
        exec_results = []
        script_path = ""
        lines = 0
        if hasattr(self, 'current_job_state'):
            job_state = self.current_job_state
            job = job_state["job"]
            pstate = job_state["pipeline_state"]
            
            worker = self.workers.get("code")
            if worker:
                res = worker.process(job, pstate)
                status_val = res.status.value
                exec_results.append({"code_generation": status_val})
                if status_val == "failed":
                    if "Health check failed" in res.reason:
                        h_reason = res.reason.replace("Health check failed: ", "").replace("Health check & Recovery failed: ", "")
                        raise RuntimeError(f"Health check failed for code: {h_reason}")
                    raise RuntimeError(f"code_generation failed: {res.reason}")
                
                script_path = res.data.get("script_path", "")
                if script_path and Path(script_path).exists():
                    lines = len(Path(script_path).read_text(encoding="utf-8").splitlines())
                
        return {"execution_results": exec_results, "lines": lines, "script_path": script_path}
