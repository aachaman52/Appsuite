import unittest
import time
from pathlib import Path

from appsuite.db import Database
from appsuite.core.event_bus import EventBus
from appsuite.core.runtime_engine import RuntimeExecutionEngine, RuntimeContext, RuntimeState, DynamicDAG
from appsuite.core.state import WorkerResult, WorkerStatus

class DummyWorker:
    def __init__(self, name: str, fail_times: int = 0):
        self.name = name
        self.fail_times = fail_times
        self.attempts = 0
        
    def run(self, job, state):
        if self.attempts < self.fail_times:
            self.attempts += 1
            return WorkerResult(status=WorkerStatus.FAILED, reason="Simulated Crash")
        return WorkerResult(status=WorkerStatus.SUCCESS, data={})

class TestRuntimeEngine(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_runtime.db")
        if self.db_path.exists():
            self.db_path.unlink()
        self.db = Database(self.db_path)
        self.bus = EventBus()
        self.events_received = []
        
        # Subscribe to all events for assertions
        def on_event(event_type, data):
            self.events_received.append((event_type, data))
        
        self.bus.subscribe("*", on_event)
        
    def tearDown(self):
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_successful_execution(self):
        workers = {
            "internet": DummyWorker("internet"),
            "godot": DummyWorker("godot")
        }
        engine = RuntimeExecutionEngine(self.db, workers, self.bus)
        
        ctx = engine.execute({"id": "job1"}, ["internet", "godot"])
        
        self.assertEqual(ctx.current_state, RuntimeState.COMPLETED)
        self.assertEqual(len(ctx.workers_finished), 2)
        
        # Check events
        event_types = [e[0] for e in self.events_received]
        self.assertIn("PipelineStarted", event_types)
        self.assertIn("WorkerStarted", event_types)
        self.assertIn("WorkerFinished", event_types)
        self.assertIn("PipelineCompleted", event_types)

    def test_worker_crash_and_dynamic_dag_repair(self):
        workers = {
            "blender": DummyWorker("blender", fail_times=3), # Fails 3 times (retries), then 4th time (after repair) it succeeds
            "improver": DummyWorker("improver")
        }
        engine = RuntimeExecutionEngine(self.db, workers, self.bus)
        
        # We start with only blender. It crashes. DAG dynamically injects 'improver'.
        ctx = engine.execute({"id": "job2"}, ["blender"])
        
        # It retries up to 3 times before applying failure rule, or it applies failure rule.
        # Currently, if retries > 3, it injects 'improver'. Improver succeeds.
        # It finishes.
        self.assertIn("improver", ctx.workers_finished)
        self.assertEqual(ctx.current_state, RuntimeState.COMPLETED)

    def test_checkpoint_recovery(self):
        workers = {
            "internet": DummyWorker("internet"),
            "godot": DummyWorker("godot")
        }
        engine = RuntimeExecutionEngine(self.db, workers, self.bus)
        
        # Simulate a crash right after internet finished.
        checkpoint = {
            "job_id": "job3",
            "workers_remaining": ["godot"],
            "workers_finished": ["internet"],
            "current_worker": "internet",
            "assets": []
        }
        
        ctx = engine.execute({"id": "job3"}, ["internet", "godot"], checkpoint=checkpoint)
        
        # Should resume from 'godot'
        self.assertEqual(ctx.workers_finished, ["internet", "godot"])
        self.assertEqual(ctx.current_state, RuntimeState.COMPLETED)

    def test_dynamic_dag_modification(self):
        dag = DynamicDAG(["internet", "analysis", "godot"])
        dag.pop_next() # internet
        self.assertEqual(dag.sequence, ["analysis", "godot"])
        
        dag.prepend("blender")
        self.assertEqual(dag.sequence, ["blender", "analysis", "godot"])

if __name__ == "__main__":
    unittest.main()
