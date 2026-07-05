import unittest
from typing import Any, Dict

from appsuite.agents.base_agent import AgentTask, AgentPlan, AgentResult, ReflectionResult, BaseAgent
from appsuite.agents.message_bus import MessageBus


class ReflectionTestAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attempts = 0

    def receive_task(self, task: AgentTask):
        pass

    def plan(self, task: AgentTask) -> Any:
        return ["step"]

    def execute_tools(self, plan: Any) -> Any:
        self.attempts += 1
        return {"status": "ok"} if self.attempts > 1 else {"status": "needs_fix"}

    def reflect(self, task: AgentTask, result: AgentResult) -> ReflectionResult:
        if self.attempts == 1:
            return ReflectionResult(success=False, gaps=["first pass incomplete"], repair_actions=["retry"])
        return ReflectionResult(success=True)

    def repair(self, task: AgentTask, reflection: ReflectionResult) -> AgentPlan:
        return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["step"])


class TestPhase9Agents(unittest.TestCase):
    def test_agent_internal_reflection_and_repair(self):
        agent = ReflectionTestAgent("ReflectionAgent", None, None, None, None, None, None)
        task = AgentTask(task_id="t1", agent_type="TestAgent", objective="test reflection")
        result = agent.run(task)

        self.assertEqual(result.status, "success")
        self.assertEqual(agent.attempts, 2)
        self.assertEqual(result.output["status"], "ok")

    def test_agent_plan_list_conversion(self):
        agent = ReflectionTestAgent("ReflectionAgent", None, None, None, None, None, None)
        plan = agent.plan(AgentTask(task_id="t2", agent_type="TestAgent", objective="parse"))
        self.assertIsInstance(plan, list)
        normalized = agent._normalize_plan(AgentTask(task_id="t2", agent_type="TestAgent", objective="parse"), plan)
        self.assertEqual(normalized.subtasks, ["step"])
        self.assertEqual(normalized.task_id, "t2")

    def test_message_bus_request_response(self):
        bus = MessageBus()
        response_queue = bus.subscribe("delegate.TestAgent")

        def responder():
            msg = response_queue.get(timeout=1)
            bus.respond(msg["reply_to"], {"result": "ok"})

        import threading
        t = threading.Thread(target=responder, daemon=True)
        t.start()

        result = bus.request("delegate.TestAgent", {"objective": "help"}, timeout=2.0)
        self.assertEqual(result, {"result": "ok"})


if __name__ == "__main__":
    unittest.main()
