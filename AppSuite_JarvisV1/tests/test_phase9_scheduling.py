import unittest
from typing import Any, Dict

from appsuite.agents.base_agent import AgentTask, AgentResult
from appsuite.engine.orchestrator import GraphOrchestrator


class DummyHardware:
    def resources(self) -> Dict[str, Any]:
        return {"ram_percent": 70.0, "cpu_percent": 10.0, "gpu_available": False}


class DummyAgent:
    def __init__(self):
        self.executed = []

    def run(self, task: AgentTask) -> AgentResult:
        self.executed.append(task.task_id)
        return AgentResult(
            agent_name=task.agent_type,
            task=task.objective,
            status="success",
            output={"task_id": task.task_id},
            confidence=1.0,
            execution_time=0.1,
        )


class TestPhase9Scheduling(unittest.TestCase):
    def test_graph_orchestrator_uses_worker_scores_and_completes(self):
        orchestrator = GraphOrchestrator()
        orchestrator.add_node("AssetAgent", DummyAgent())
        orchestrator.add_node("CodeAgent", DummyAgent())

        tasks = [
            AgentTask(task_id="task1", agent_type="AssetAgent", objective="find assets", priority=2, estimated_duration_seconds=5.0),
            AgentTask(task_id="task2", agent_type="CodeAgent", objective="generate code", priority=1, estimated_duration_seconds=3.0),
        ]
        job_state = {"job": {"id": "sched-test"}, "pipeline_state": {}}

        results = orchestrator.run_dag(tasks, job_state, DummyHardware(), worker_scores={"AssetAgent": 0.4, "CodeAgent": 0.8})
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == "success" for r in results))


if __name__ == "__main__":
    unittest.main()
