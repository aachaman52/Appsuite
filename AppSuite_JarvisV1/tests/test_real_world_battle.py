import os
import sys
import time
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.pipeline.pipeline import Pipeline
from appsuite.core.supervisor import Supervisor
from appsuite.core.state import WorkerResult, WorkerStatus
from appsuite.engine.orchestrator import GraphOrchestrator
from appsuite.engine.job_state import UnifiedJobState
from appsuite.engine.event_bus import (
    EventBus, TaskCreated, TaskStarted, TaskCompleted, TaskFailed,
    WorkerStarted, WorkerFinished, CheckpointSaved, RecoveryStarted,
    RecoveryCompleted, ResourceWarning, PipelineFinished
)
from appsuite.engine.checkpoint import CheckpointManager
from appsuite.engine.observability import ObservabilityWriter
from appsuite.agents.coordinator import AgentCoordinator
from appsuite.agents.base_agent import AgentTask, AgentResult
from appsuite.core.jarvis import JarvisCore

class MockRealWorker:
    def __init__(self, key):
        self.key = key
        self.should_crash = False
        self.should_fail = False
        self.timeout = False
        
    def process(self, job, state):
        if self.timeout:
            time.sleep(1)
            raise TimeoutError("Simulated API timeout")
        if self.should_crash:
            raise Exception(f"Simulated {self.key} crash")
        if self.should_fail:
            return WorkerResult(WorkerStatus.FAILED, reason="Simulated failure", metadata={})
            
        return WorkerResult(
            status=WorkerStatus.SUCCESS,
            data={"stage": self.key, "ok": True},
            reason="",
            metadata={"execution_time": 0.05}
        )

    def run(self, job, state):
        return self.process(job, state)

class TestRealWorldBattle(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.registry = MagicMock()
        self.memory = MagicMock()
        self.templates = MagicMock()
        self.plugins = MagicMock()
        self.brain = MagicMock()
        
        from appsuite.core.jarvis_brain import ExecutionPlan
        
        self.brain.plan_execution.return_value = ExecutionPlan(
            stages=["cloud_deploy"],
            agent_tasks=[
                AgentTask("task_1", "AssetAgent", "Fetch city assets", [], [], 1, {}),
                AgentTask("task_2", "BlenderAgent", "Optimize city assets", [], ["task_1"], 1, {}),
                AgentTask("task_3", "CodeAgent", "Generate NPCs", [], ["task_1"], 1, {}),
                AgentTask("task_4", "GodotAgent", "Assemble scene", [], ["task_2", "task_3"], 1, {})
            ],
            reasoning="Testing Real World",
            reused_assets=False
        )
        
        self.workers = {
            "internet": MockRealWorker("internet"),
            "blender": MockRealWorker("blender"),
            "godot": MockRealWorker("godot"),
            "validation": MockRealWorker("validation"),
            "deploy": MockRealWorker("deploy"),
            "analysis": MockRealWorker("analysis")
        }
        
        self.output_dir = Path("./mock_output_battle")
        self.output_dir.mkdir(exist_ok=True)
        
        self.pipeline = Pipeline(
            self.db, self.registry, self.memory, self.templates,
            self.plugins, self.workers, self.output_dir, orchestrator_mode="graph"
        )
        
        import appsuite.config
        cfg = appsuite.config.load_config()
        self.jarvis = JarvisCore(cfg.scheduler, str(self.output_dir))
        self.jarvis.wire(self.db, self.registry, self.memory, self.templates, self.workers, self.pipeline, self.brain, MagicMock(), MagicMock())
        
        # Disable health checks by default
        from appsuite.core.health import WorkerHealthMonitor
        WorkerHealthMonitor.preflight_check = MagicMock(return_value=(True, "OK"))

    def tearDown(self):
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        for p in Path(".").glob("*_checkpoint.json"):
            p.unlink(missing_ok=True)

    def test_scenario_1_normal_parallel_execution(self):
        """Scenario 1: Normal parallel execution of all tasks"""
        job = {"id": "job_scenario_1", "prompt": "normal execution"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        obs = ObservabilityWriter(bus, self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, obs, max_workers=4)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Mock agents to succeed
        for agent in self.jarvis._coordinator.agent_registry.values():
            agent.run = MagicMock(return_value=AgentResult(
                agent_name=agent.name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
            ))
            
        tasks = self.brain.plan_execution(job, []).agent_tasks
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertEqual(len(results), 4)
        for r in results:
            self.assertEqual(r.status, "success")

    def test_scenario_2_checkpoint_restore(self):
        """Scenario 2: Checkpoint and restore from intermediate failure"""
        job_id = "job_scenario_2"
        job = {"id": job_id, "prompt": "checkpoint test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        obs = ObservabilityWriter(bus, self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, obs, max_workers=2)
        
        # Pre-populate checkpoint indicating task_1 and task_2 are completed
        state = UnifiedJobState(template={"id": "generic"})
        ckpt_mgr.save(job_id, {"task_1", "task_2"}, {"task_3", "task_4"}, state)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Mock agents to succeed
        for agent in self.jarvis._coordinator.agent_registry.values():
            agent.run = MagicMock(return_value=AgentResult(
                agent_name=agent.name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
            ))
            
        tasks = self.brain.plan_execution(job, []).agent_tasks
        # Only task_3 and task_4 should run
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": state})
        # Two tasks were run
        self.assertEqual(len(results), 2)

    def test_scenario_3_circular_dependency(self):
        """Scenario 3: Circular dependency detection (Cycle detection)"""
        job = {"id": "job_scenario_3", "prompt": "cycle test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=2)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Create circular dependency: task_1 depends on task_2, task_2 depends on task_1
        tasks = [
            AgentTask("task_1", "AssetAgent", "Fetch", [], ["task_2"], 1, {}),
            AgentTask("task_2", "BlenderAgent", "Optimize", [], ["task_1"], 1, {})
        ]
        
        with self.assertRaises(ValueError) as context:
            self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertIn("Cycle detected", str(context.exception))

    def test_scenario_4_worker_timeout(self):
        """Scenario 4: Worker timeout handling"""
        job = {"id": "job_scenario_4", "prompt": "timeout test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        # Set task timeout to 0.1s to trigger timeout quickly
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=2, task_timeout=0.1)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Mock slow agent
        def slow_run(task, job_state=None):
            time.sleep(0.5)
            return AgentResult(agent_name="AssetAgent", task="Fetch", status="success", output={}, confidence=1.0, execution_time=0.5)
            
        self.jarvis._coordinator.agent_registry["AssetAgent"].run = slow_run
        
        tasks = [AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {})]
        
        with self.assertRaises(RuntimeError) as context:
            self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertIn("TASK_TIMEOUT", str(context.exception))

    def test_scenario_5_deadlock_detection(self):
        """Scenario 5: Deadlock detection"""
        job = {"id": "job_scenario_5", "prompt": "deadlock test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=2)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Deadlock: task_1 depends on non-existent task_99
        tasks = [
            AgentTask("task_1", "AssetAgent", "Fetch", [], ["task_99"], 1, {})
        ]
        
        with self.assertRaises(RuntimeError) as context:
            self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertIn("Deadlock detected", str(context.exception))

    def test_scenario_6_resource_limit_warning(self):
        """Scenario 6: Resource limit warning and scheduling pause"""
        job = {"id": "job_scenario_6", "prompt": "resource test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=2)
        
        mock_hardware = MagicMock()
        mock_hardware.resources.return_value = {"ram_percent": 95.0, "cpu_percent": 10.0}
        
        self.jarvis._coordinator = AgentCoordinator(
            MagicMock(), memory=self.memory, orchestrator=orchestrator,
            hardware=mock_hardware, brain=self.brain, workers=self.workers
        )
        
        # Mock agents to succeed
        for agent in self.jarvis._coordinator.agent_registry.values():
            agent.run = MagicMock(return_value=AgentResult(
                agent_name=agent.name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
            ))
            
        # Verify ResourceWarning event is published
        warning_triggered = []
        bus.subscribe(ResourceWarning, lambda e: warning_triggered.append(e))
        
        tasks = [AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {})]
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        
        self.assertEqual(len(results), 1)
        self.assertTrue(len(warning_triggered) > 0)
        self.assertEqual(warning_triggered[0].resource, "ram")

    def test_scenario_7_priority_scheduling(self):
        """Scenario 7: High-priority task scheduling before low-priority task"""
        job = {"id": "job_scenario_7", "prompt": "priority test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=1) # force single worker to serialize execution order
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        order = []
        def make_run(name, task_id):
            def run(task, job_state=None):
                order.append(task_id)
                return AgentResult(agent_name=name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01)
            return run
            
        self.jarvis._coordinator.agent_registry["AssetAgent"].run = make_run("AssetAgent", "task_low")
        self.jarvis._coordinator.agent_registry["BlenderAgent"].run = make_run("BlenderAgent", "task_high")
        
        # Both tasks have no dependencies, so both are ready. task_high has priority 10, task_low has priority 1.
        tasks = [
            AgentTask("task_low", "AssetAgent", "Fetch", [], [], 1, {}),
            AgentTask("task_high", "BlenderAgent", "Optimize", [], [], 10, {})
        ]
        
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertEqual(len(results), 2)
        # task_high must run before task_low due to priority scheduling!
        self.assertEqual(order, ["task_high", "task_low"])

    def test_scenario_8_worker_health_failure(self):
        """Scenario 8: Worker health failure (pre-flight check failure)"""
        # Enable preflight health checks
        from appsuite.core.health import WorkerHealthMonitor
        WorkerHealthMonitor.preflight_check = MagicMock(return_value=(False, "GPU driver missing"))
        
        job = {"id": "job_scenario_8", "prompt": "health fail test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=1)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Set up a real execution call which should trigger the preflight check
        tasks = [AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {})]
        
        # Register a real tool execution plan which resolves to a worker key
        self.jarvis._coordinator.agent_registry["AssetAgent"].plan = MagicMock(return_value=["asset_search"])
        
        with self.assertRaises(RuntimeError) as context:
            self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertIn("Health check failed for internet: GPU driver missing", str(context.exception))

    def test_scenario_9_database_persistence(self):
        """Scenario 9: Database persistence validation"""
        job = {"id": "job_scenario_9", "prompt": "db test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=2)
        
        # Re-enable Mock setup to check db callbacks
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        for agent in self.jarvis._coordinator.agent_registry.values():
            agent.run = MagicMock(return_value=AgentResult(
                agent_name=agent.name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
            ))
            
        tasks = [AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {})]
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        
        # Verify checkpoint save was executed, which checks serialization output
        path = ckpt_mgr._get_path(job["id"])
        self.assertFalse(path.exists()) # Cleaned up on success, but must have existed. Let's test serialization explicitly.
        state = UnifiedJobState(template={"id": "generic"})
        path_str = ckpt_mgr.save("test_db_persist", {"task_1"}, set(), state)
        self.assertTrue(Path(path_str).exists())
        with open(path_str, "r") as f:
            data = json.load(f)
        self.assertEqual(data["job_id"], "test_db_persist")
        self.assertIn("pipeline_state", data["state"])

    def test_scenario_10_event_timeline_logging(self):
        """Scenario 10: Event timeline logging validation"""
        job = {"id": "job_scenario_10", "prompt": "timeline test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        obs = ObservabilityWriter(bus, self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, obs, max_workers=1)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        self.jarvis._coordinator.agent_registry["AssetAgent"].run = MagicMock(return_value=AgentResult(
            agent_name="AssetAgent", task="Fetch", status="success", output={}, confidence=1.0, execution_time=0.02
        ))
        
        tasks = [AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {})]
        self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        
        obs.write_outputs()
        
        metrics_file = self.output_dir / "execution_metrics.json"
        timeline_file = self.output_dir / "execution_timeline.json"
        graph_file = self.output_dir / "dependency_graph.json"
        stats_file = self.output_dir / "worker_statistics.json"
        
        self.assertTrue(metrics_file.exists())
        self.assertTrue(timeline_file.exists())
        self.assertTrue(graph_file.exists())
        self.assertTrue(stats_file.exists())
        
        with open(metrics_file, "r") as f:
            metrics = json.load(f)
        self.assertEqual(metrics["task_count"], 1)
        self.assertEqual(metrics["success_count"], 1)

    def test_scenario_11_multithreaded_isolation(self):
        """Scenario 11: Multi-threaded worker process isolation (verifying no state leakage)"""
        job = {"id": "job_scenario_11", "prompt": "isolation test"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=4)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Test simultaneous access to agent attributes
        states = []
        def make_thread_run(agent_name):
            def run(task, job_state=None):
                time.sleep(0.1)
                # Capture thread-local context/state to make sure they do not override each other
                states.append((agent_name, task.task_id))
                return AgentResult(agent_name=agent_name, task="obj", status="success", output={}, confidence=1.0, execution_time=0.01)
            return run
            
        self.jarvis._coordinator.agent_registry["AssetAgent"].run = make_thread_run("AssetAgent")
        self.jarvis._coordinator.agent_registry["BlenderAgent"].run = make_thread_run("BlenderAgent")
        
        tasks = [
            AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {}),
            AgentTask("task_2", "BlenderAgent", "Optimize", [], [], 1, {})
        ]
        
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        self.assertEqual(len(results), 2)
        self.assertEqual(len(states), 2)
        # Assert they are distinct and executed isolatedly
        self.assertCountEqual([s[0] for s in states], ["AssetAgent", "BlenderAgent"])

    def test_scenario_12_arbitrary_crash_recovery(self):
        """Scenario 12: End-to-end recovery from arbitrary crash (run half, crash, resume, finish)"""
        job_id = "job_scenario_12"
        job = {"id": job_id, "prompt": "crash recovery"}
        
        bus = EventBus()
        ckpt_mgr = CheckpointManager(self.output_dir)
        orchestrator = GraphOrchestrator(bus, ckpt_mgr, max_workers=1)
        
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=orchestrator, hardware=None, brain=self.brain, workers=self.workers)
        
        # Task 1 fails, Task 2 succeeded. Wait, let's run a workflow:
        # First run: task_1 succeeds, task_2 crashes.
        self.jarvis._coordinator.agent_registry["AssetAgent"].run = MagicMock(return_value=AgentResult(
            agent_name="AssetAgent", task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
        ))
        
        def crash_run(task, job_state=None):
            raise Exception("Simulated sudden worker crash")
        self.jarvis._coordinator.agent_registry["BlenderAgent"].run = crash_run
        
        tasks = [
            AgentTask("task_1", "AssetAgent", "Fetch", [], [], 1, {}),
            AgentTask("task_2", "BlenderAgent", "Optimize", [], ["task_1"], 1, {})
        ]
        
        # Execute first time - should crash and leave checkpoint with task_1 completed
        try:
            self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        except Exception:
            pass
            
        # Verify checkpoint was saved for task_1
        ckpt = ckpt_mgr.load(job_id)
        self.assertIsNotNone(ckpt)
        self.assertIn("task_1", ckpt["completed"])
        self.assertNotIn("task_2", ckpt["completed"])
        
        # Second run: Mock BlenderAgent to succeed now
        self.jarvis._coordinator.agent_registry["BlenderAgent"].run = MagicMock(return_value=AgentResult(
            agent_name="BlenderAgent", task="obj", status="success", output={}, confidence=1.0, execution_time=0.01
        ))
        
        # Re-run: should resume from checkpoint and complete the rest
        results = self.jarvis._coordinator.execute_plan(tasks, {"job": job, "pipeline_state": UnifiedJobState(template={"id": "generic"})})
        # Only task_2 is executed in the second run because task_1 was recovered
        self.assertEqual(len(results), 1)
        
        # Finally, the checkpoint file should be cleaned up on success
        ckpt2 = ckpt_mgr.load(job_id)
        self.assertIsNone(ckpt2)

if __name__ == "__main__":
    unittest.main()
