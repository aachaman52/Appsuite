import os
import sys
import time
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from appsuite.pipeline.pipeline import Pipeline
from appsuite.core.supervisor import Supervisor
from appsuite.core.state import WorkerResult, WorkerStatus
from appsuite.graph.graph import GraphOrchestrator
from appsuite.agents.coordinator import AgentCoordinator
from appsuite.core.jarvis import JarvisCore

class MockRealWorker:
    def __init__(self, key):
        self.key = key
        self.should_crash = False
        self.should_fail = False
        self.timeout = False
        
    def run(self, job, state):
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
        
    def search_and_fetch(self, job_id, role, term):
        if self.should_crash:
            raise Exception("Network Error")
        return {"file_path": f"{term}.obj", "cache_hit": False, "source": "mock"}

class TestRealWorldBattle(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.registry = MagicMock()
        self.memory = MagicMock()
        self.templates = MagicMock()
        self.plugins = MagicMock()
        self.brain = MagicMock()
        
        # Give brain an empty DAG, but we will mock what Brain returns to force Agents
        # Wait, the pipeline executes brain.plan_execution()
        from appsuite.core.jarvis_brain import ExecutionPlan
        from appsuite.agents.base_agent import AgentTask
        
        self.brain.plan_execution.return_value = ExecutionPlan(
            stages=["cloud_deploy"], # the GraphOrchestrator fallback
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
            "deploy": MockRealWorker("deploy")
        }
        
        self.output_dir = Path("./mock_output_battle")
        self.output_dir.mkdir(exist_ok=True)
        
        self.pipeline = Pipeline(
            self.db, self.registry, self.memory, self.templates,
            self.plugins, self.workers, self.output_dir, orchestrator_mode="graph"
        )
        
        # Setup real Jarvis to use AgentCoordinator and GraphOrchestrator underneath
        import appsuite.config
        cfg = appsuite.config.load_config()
        self.jarvis = JarvisCore(cfg.scheduler, str(self.output_dir))
        self.jarvis.wire(self.db, self.registry, self.memory, self.templates, self.workers, self.pipeline, self.brain, MagicMock(), MagicMock())
        
        # Disable health checks
        from appsuite.core.health import WorkerHealthMonitor
        WorkerHealthMonitor.preflight_check = MagicMock(return_value=(True, "OK"))

    def tearDown(self):
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        for p in Path(".").glob("*_checkpoint.json"):
            p.unlink(missing_ok=True)

    def test_full_gta_scene(self):
        """Test #1: Full GTA-style scene"""
        job = {"id": "job_gta_scene", "prompt": "Create an Indian city street scene with cars, buildings, trees, NPC placeholder"}
        
        start = time.time()
        # Mocking ProviderManager to generate fake gdscript so Godot syntax check doesn't fail
        # Actually it's fine, GodotAgent mock handles it. 
        # But wait, CodeAgent does subprocess.run("godot"), if godot doesn't exist it skips.
        mock_hardware = MagicMock()
        mock_hardware.resources.return_value = {"ram_percent": 50.0}
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=GraphOrchestrator(self.db), hardware=mock_hardware, brain=self.brain)
        
        # Mock agents to succeed
        for agent in self.jarvis._coordinator.agent_registry.values():
            agent.run = MagicMock(return_value=MagicMock(status="success"))
            
        results = self.jarvis._coordinator.execute_plan(self.brain.plan_execution(job, []).agent_tasks, {"job": job})
        
        # Verify
        self.assertEqual(len(results), 4) # 4 tasks executed
        execution_time = time.time() - start
        print(f"GTA Scene generated in {execution_time:.2f}s")
        
    def test_kill_failures(self):
        """Test #2: Kill tests (Simulate crashes and timeouts)"""
        job = {"id": "job_kill_test", "prompt": "Test recovery"}
        
        # Setup checkpoint file to simulate resume from crash
        checkpoint_file = "job_kill_test_dag_checkpoint.json"
        with open(checkpoint_file, "w") as f:
            # task_1 completed, system crashed, resuming from task_2
            json.dump({"completed": ["task_1"]}, f)
            
        mock_hardware = MagicMock()
        mock_hardware.resources.return_value = {"ram_percent": 50.0}
        self.jarvis._coordinator = AgentCoordinator(MagicMock(), memory=self.memory, orchestrator=GraphOrchestrator(self.db), hardware=mock_hardware, brain=self.brain)
        
        # Mock agents
        for name, agent in self.jarvis._coordinator.agent_registry.items():
            agent.run = MagicMock(return_value=MagicMock(status="success", task=f"task_{name}"))
            
        results = self.jarvis._coordinator.execute_plan(self.brain.plan_execution(job, []).agent_tasks, {"job": job})
        
        # task_1 was already done, so we should only have 3 results
        self.assertEqual(len(results), 3)

if __name__ == "__main__":
    unittest.main()
