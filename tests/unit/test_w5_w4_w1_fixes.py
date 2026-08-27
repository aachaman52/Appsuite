"""
Tests for W5 (thread safety), W4 (retry architecture), and W1 (execution engine).

These tests verify:
  - W5: Agents are stateless; parallel execution produces isolated, uncorrupted results.
  - W4: Supervisor dispatches jobs exactly once (no retry loop).
  - W1: Deprecation warning is emitted by orchestrator.run() (legacy sequential path).
  - Regression: existing behaviour of BaseAgent reflect/repair loop still works.
"""
from __future__ import annotations

import sys
import threading
import time
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from appsuite.agents.base_agent import (
    AgentPlan,
    AgentResult,
    AgentTask,
    BaseAgent,
    ReflectionResult,
)
from appsuite.agents.asset_agent import AssetAgent
from appsuite.agents.blender_agent import BlenderAgent
from appsuite.agents.godot_agent import GodotAgent
from appsuite.agents.code_agent import CodeAgent
from appsuite.agents.browser_agent import BrowserAgent
from appsuite.agents.message_bus import MessageBus


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_job_state(job_id: str, tag: str = "") -> Dict[str, Any]:
    """Return a minimal isolated job_state dict for testing."""
    return {
        "job": {"id": job_id, "prompt": f"test job {tag}", "template_id": "generic_scene"},
        "pipeline_state": MagicMock(),
    }


class _CountingAgent(BaseAgent):
    """
    Test agent that records the job_id from every execution.
    Used to verify that parallel threads never see each other's job_state.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_job_ids: List[str] = []
        self._lock = threading.Lock()

    def plan(self, task: AgentTask, job_state: Optional[Dict[str, Any]] = None) -> List[str]:
        return ["step"]

    def execute_tools(self, plan: Any, job_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Short sleep to maximise thread interleaving
        time.sleep(0.01)
        job_id = (job_state or {}).get("job", {}).get("id", "MISSING")
        with self._lock:
            self._seen_job_ids.append(job_id)
        return {"job_id_seen": job_id}

    @property
    def seen_job_ids(self) -> List[str]:
        with self._lock:
            return list(self._seen_job_ids)


# ─── W5: Thread Safety Tests ───────────────────────────────────────────────────

class TestW5ThreadSafety(unittest.TestCase):
    """
    Verify that agents are stateless w.r.t. job_state and can be called
    concurrently from multiple threads without state corruption.
    """

    def test_single_agent_parallel_invocations_isolated(self):
        """
        The SAME agent instance is called N times in parallel.
        Each call must observe only its own job_state (identified by a unique job_id).
        No call may observe another call's job_id.
        """
        agent = _CountingAgent("CountingAgent", None, None, None)
        n_jobs = 20
        job_ids = [str(uuid.uuid4()) for _ in range(n_jobs)]

        results: List[AgentResult] = []
        results_lock = threading.Lock()

        def run_agent(job_id: str) -> None:
            task = AgentTask(task_id=f"t-{job_id[:8]}", agent_type="_CountingAgent", objective="parallel test")
            state = _make_job_state(job_id, tag=job_id[:8])
            result = agent.run(task, job_state=state)
            with results_lock:
                results.append(result)

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(run_agent, jid) for jid in job_ids]
            for f in as_completed(futures):
                f.result()  # propagate any exception

        # Every result must carry the correct job_id — no cross-contamination
        self.assertEqual(len(results), n_jobs)
        self.assertEqual(len(agent.seen_job_ids), n_jobs)
        for job_id in job_ids:
            self.assertIn(job_id, agent.seen_job_ids,
                          f"job_id {job_id[:8]} was not recorded — state was corrupted")

        # Each job_id must appear exactly once
        seen_counts = {}
        for jid in agent.seen_job_ids:
            seen_counts[jid] = seen_counts.get(jid, 0) + 1
        for jid, count in seen_counts.items():
            self.assertEqual(count, 1,
                             f"job_id {jid[:8]} appeared {count} times — state leaked between threads")

    def test_no_current_job_state_attribute_on_base_agent(self):
        """
        BaseAgent must NOT set current_job_state as an instance attribute.
        Verifying absence of the shared-state anti-pattern.
        """
        agent = _CountingAgent("TestAgent", None, None, None)
        self.assertFalse(
            hasattr(agent, "current_job_state"),
            "current_job_state should NOT exist as an instance attribute — it was the source of the W5 data race",
        )

    def test_asset_agent_execute_with_no_workers_is_safe(self):
        """AssetAgent.execute_tools with no workers must not raise."""
        agent = AssetAgent("AssetAgent", None, None, None, None, {}, None)
        task = AgentTask(task_id="t1", agent_type="AssetAgent", objective="test")
        state = _make_job_state("job-asset-1")
        result = agent.run(task, job_state=state)
        # Should succeed even with no workers (returns empty execution_results)
        self.assertIn(result.status, ("success",))

    def test_blender_agent_execute_with_no_workers_is_safe(self):
        """BlenderAgent.execute_tools with no workers must not raise."""
        agent = BlenderAgent("BlenderAgent", None, None, None, None, {}, None)
        task = AgentTask(task_id="t2", agent_type="BlenderAgent", objective="test")
        state = _make_job_state("job-blender-1")
        result = agent.run(task, job_state=state)
        self.assertIn(result.status, ("success",))

    def test_godot_agent_execute_with_no_workers_is_safe(self):
        """GodotAgent.execute_tools with no workers must not raise."""
        agent = GodotAgent("GodotAgent", None, None, None, None, {}, None)
        task = AgentTask(task_id="t3", agent_type="GodotAgent", objective="test")
        state = _make_job_state("job-godot-1")
        result = agent.run(task, job_state=state)
        self.assertIn(result.status, ("success",))

    def test_code_agent_execute_with_no_workers_is_safe(self):
        """CodeAgent.execute_tools with no workers must not raise."""
        agent = CodeAgent("CodeAgent", None, None, None, None, {}, None)
        task = AgentTask(task_id="t4", agent_type="CodeAgent", objective="test")
        state = _make_job_state("job-code-1")
        result = agent.run(task, job_state=state)
        self.assertIn(result.status, ("success",))

    def test_agent_run_without_job_state_uses_empty_dict(self):
        """
        Calling agent.run(task) without a job_state must not raise —
        it defaults to an empty dict safely.
        """
        agent = _CountingAgent("CountingAgent", None, None, None)
        task = AgentTask(task_id="t5", agent_type="_CountingAgent", objective="no state test")
        result = agent.run(task)  # No job_state kwarg
        self.assertEqual(result.status, "success")

    def test_stress_50_agents_in_parallel(self):
        """
        Stress test: 50 parallel invocations on a single agent instance.
        All must complete successfully with isolated state.
        """
        agent = _CountingAgent("StressAgent", None, None, None)
        n = 50
        job_ids = [str(uuid.uuid4()) for _ in range(n)]
        errors: List[str] = []
        errors_lock = threading.Lock()

        def run_one(jid: str) -> None:
            task = AgentTask(task_id=f"s-{jid[:6]}", agent_type="StressAgent", objective="stress")
            result = agent.run(task, job_state=_make_job_state(jid))
            if result.status != "success":
                with errors_lock:
                    errors.append(f"job {jid[:8]} failed: {result.output}")
            seen = result.output.get("job_id_seen")
            if seen != jid:
                with errors_lock:
                    errors.append(f"State corruption: expected {jid[:8]} got {seen}")

        with ThreadPoolExecutor(max_workers=20) as ex:
            list(as_completed([ex.submit(run_one, jid) for jid in job_ids]))

        self.assertEqual(errors, [], f"Parallel execution errors:\n" + "\n".join(errors))


# ─── W4: Retry Architecture Tests ─────────────────────────────────────────────

class TestW4RetryArchitecture(unittest.TestCase):
    """
    Verify that the Supervisor no longer retries jobs internally.
    It dispatches once; retry ownership belongs to the worker and StateGraph.
    """

    def _make_supervisor(self, pipeline_mock):
        """Create a minimal Supervisor with mocked dependencies."""
        import tempfile
        from appsuite.db import Database
        from appsuite.core.supervisor import Supervisor

        db_file = Path(tempfile.mktemp(suffix=".db"))
        self._db_files.append(db_file)
        db = Database(db_file)
        self._dbs.append(db)

        memory = MagicMock()
        memory.remember = MagicMock()
        jarvis = MagicMock()
        jarvis.can_schedule.return_value = (True, "ok")

        return Supervisor(
            db=db,
            jarvis=jarvis,
            pipeline=pipeline_mock,
            memory=memory,
            scheduler_cfg={"max_concurrent_jobs": 1, "poll_interval_seconds": 0.05},
            retries_cfg={"max_attempts": 3, "backoff_seconds": 0.0},
        ), db

    def setUp(self):
        self._db_files: List[Path] = []
        self._dbs = []

    def tearDown(self):
        import gc
        for db in self._dbs:
            try:
                db.close()
            except Exception:
                pass
        gc.collect()
        time.sleep(0.1)
        for f in self._db_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

    def test_supervisor_dispatches_job_exactly_once_on_success(self):
        """On success, the pipeline is called exactly once by the Supervisor."""
        execute_count = {"n": 0}

        class OncePipeline:
            def execute(self, job):
                execute_count["n"] += 1
                return {"template": "generic_scene"}

        sup, db = self._make_supervisor(OncePipeline())
        job_id = sup.submit("test prompt")
        sup.start()

        # Wait for job to complete
        for _ in range(40):
            row = db.get_job(job_id)
            if row and row["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)

        sup.stop()
        self.assertEqual(execute_count["n"], 1,
                         "Supervisor must dispatch exactly once on success")
        row = db.get_job(job_id)
        self.assertEqual(row["status"], "completed")

    def test_supervisor_dispatches_job_exactly_once_on_failure(self):
        """
        On pipeline failure, the Supervisor records the failure once and does NOT retry.
        Retry responsibility belongs to the worker (BaseWorker.with_retry) and
        the StateGraph replan node — not the Supervisor.
        """
        execute_count = {"n": 0}

        class FailPipeline:
            def execute(self, job):
                execute_count["n"] += 1
                raise RuntimeError("Simulated pipeline failure")

        sup, db = self._make_supervisor(FailPipeline())
        job_id = sup.submit("fail prompt")
        sup.start()

        for _ in range(40):
            row = db.get_job(job_id)
            if row and row["status"] in ("completed", "failed"):
                break
            time.sleep(0.05)

        sup.stop()

        self.assertEqual(execute_count["n"], 1,
                         "Supervisor must NOT retry on pipeline failure — "
                         "retry belongs to worker/StateGraph layers")
        row = db.get_job(job_id)
        self.assertEqual(row["status"], "failed")
        self.assertIsNotNone(row["error"])

    def test_worker_level_retry_is_independent_of_supervisor(self):
        """
        BaseWorker.with_retry handles transient tool failures independently.
        It must retry up to max_attempts without the Supervisor being involved.
        """
        from appsuite.workers.base import BaseWorker, WorkerError
        from appsuite.core.state import WorkerResult, WorkerStatus

        attempt_counter = {"n": 0}

        class FlakyWorker(BaseWorker):
            name = "flaky"

            def run(self, job, state):
                attempt_counter["n"] += 1
                if attempt_counter["n"] < 3:
                    raise RuntimeError("transient error")
                return WorkerResult(status=WorkerStatus.SUCCESS, data={"ok": True})

        worker = FlakyWorker(
            config={},
            retries={"max_attempts": 3, "backoff_seconds": 0.0, "backoff_multiplier": 1.0},
            context={},
        )
        result = worker.with_retry(
            lambda: worker.run({}, {}),
            desc="flaky_op"
        )
        self.assertEqual(result.status, WorkerStatus.SUCCESS)
        self.assertEqual(attempt_counter["n"], 3,
                         "Worker-level retry must attempt exactly 3 times")


# ─── W1: Execution Engine Consolidation / Deprecation Tests ───────────────────

class TestW1ExecutionEngineConsolidation(unittest.TestCase):
    """
    Verify the deprecation warning is emitted by the legacy sequential path
    and that the canonical path (run_dag) does not emit warnings.
    """

    def test_orchestrator_run_emits_deprecation_warning(self):
        """
        GraphOrchestrator.run() (sequential/legacy path) must emit a DeprecationWarning.
        This signals to callers that they should migrate to run_dag().
        """
        from appsuite.engine.orchestrator import GraphOrchestrator
        from appsuite.engine.job_state import UnifiedJobState

        orch = GraphOrchestrator()
        # Minimal node that returns success immediately
        from appsuite.core.state import WorkerResult, WorkerStatus

        class SuccessNode:
            def process(self, state):
                from appsuite.core.state import WorkerResult, WorkerStatus
                state.worker_result = WorkerResult(status=WorkerStatus.SUCCESS)
                state.history.append(state.current_node)
                return state

        orch.add_node("asset_search", SuccessNode())
        # Router that always ends
        class EndRouter:
            def route(self, state):
                return "END"
        orch.set_router(EndRouter())

        template = {"id": "generic_scene", "asset_slots": []}
        state = UnifiedJobState(template=template, job={"id": "w1-test", "prompt": "test"})
        job_state = {"job": {"id": "w1-test", "prompt": "test"}, "pipeline_state": state}

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            orch.run(job_state)

        depr_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertTrue(
            len(depr_warnings) >= 1,
            "GraphOrchestrator.run() must emit a DeprecationWarning to signal "
            "migration to run_dag(). None was emitted.",
        )
        self.assertIn("run_dag", str(depr_warnings[0].message))

    def test_orchestrator_run_dag_does_not_emit_deprecation_warning(self):
        """
        GraphOrchestrator.run_dag() must NOT emit a DeprecationWarning.
        It is the canonical, non-deprecated execution path.
        """
        from appsuite.engine.orchestrator import GraphOrchestrator

        orch = GraphOrchestrator()
        # run_dag with empty task list should complete cleanly
        job_state = {
            "job": {"id": "dag-no-warn", "prompt": "test"},
            "pipeline_state": MagicMock(),
        }
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                orch.run_dag([], job_state)
            except Exception:
                pass  # Empty DAG may raise — that's fine

        depr_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(
            len(depr_warnings), 0,
            f"run_dag() must NOT emit a DeprecationWarning. Got: {depr_warnings}",
        )


# ─── Regression: BaseAgent reflect/repair loop still works ───────────────────

class TestBaseAgentReflectRepairRegression(unittest.TestCase):
    """
    Ensure the reflect → repair → re-execute loop in BaseAgent still functions
    correctly after the job_state signature change.
    """

    def test_reflect_repair_cycle_with_job_state(self):
        """
        An agent that fails on first execute but succeeds after repair must
        return success and record 2 attempts.
        """
        class RepairAgent(BaseAgent):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.attempts = 0

            def plan(self, task, job_state=None):
                return ["step"]

            def execute_tools(self, plan, job_state=None):
                self.attempts += 1
                return {"ok": self.attempts > 1}

            def reflect(self, task, result, job_state=None):
                if self.attempts == 1:
                    return ReflectionResult(success=False, repair_actions=["retry"])
                return ReflectionResult(success=True)

            def repair(self, task, reflection, job_state=None):
                return AgentPlan(task_id=task.task_id, objective=task.objective, subtasks=["step"])

        agent = RepairAgent("RepairAgent", None, None, None)
        task = AgentTask(task_id="r1", agent_type="RepairAgent", objective="reflect test")
        state = _make_job_state("job-repair-1")
        result = agent.run(task, job_state=state)

        self.assertEqual(result.status, "success")
        self.assertEqual(agent.attempts, 2)
        self.assertTrue(result.output.get("ok"))

    def test_job_state_is_forwarded_to_reflect_and_repair(self):
        """
        The job_state passed to run() must be the same object forwarded to
        reflect() and repair() — agents can use it for context-aware recovery.
        """
        received_states: Dict[str, Any] = {}

        class ContextAwareAgent(BaseAgent):
            def plan(self, task, job_state=None):
                return ["step"]

            def execute_tools(self, plan, job_state=None):
                return {"attempted": True}

            def reflect(self, task, result, job_state=None):
                received_states["reflect"] = job_state
                return ReflectionResult(success=True)

            def repair(self, task, reflection, job_state=None):
                received_states["repair"] = job_state
                return None

        agent = ContextAwareAgent("CAAgt", None, None, None)
        task = AgentTask(task_id="ca1", agent_type="CAAgt", objective="ctx test")
        state = _make_job_state("job-ctx-1")
        agent.run(task, job_state=state)

        # reflect must have received the same state
        self.assertIs(received_states.get("reflect"), state,
                      "reflect() must receive the same job_state passed to run()")


if __name__ == "__main__":
    unittest.main()
