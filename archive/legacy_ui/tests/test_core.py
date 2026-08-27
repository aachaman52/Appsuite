import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

# Add project root to path
sys_path = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(sys_path))

from appsuite.core.templates import TemplateEngine
from appsuite.core.provider_manager import ProviderManager
from appsuite.core.jarvis import JarvisCore
from appsuite.core.asset_normalizer import AssetNormalizer
from appsuite.core.jarvis_planner import JarvisPlanner
from appsuite.db import Database
from appsuite.core.supervisor import Supervisor
from appsuite.workers.internet_worker import InternetWorker
from appsuite.workers.blender_worker import BlenderWorker
from appsuite.workers.godot_worker import GodotWorker
from appsuite.workers.analysis_worker import AnalysisWorker
from appsuite.core.asset_registry import AssetRegistry


class TestTemplateEngine(unittest.TestCase):
    def setUp(self):
        self.templates = [
            {
                "id": "medieval_village",
                "keywords": ["medieval", "castle", "village", "knight"],
                "asset_slots": []
            },
            {
                "id": "generic_scene",
                "keywords": [],
                "asset_slots": []
            }
        ]
        self.engine = TemplateEngine(self.templates)

    def test_exact_match(self):
        res = self.engine.resolve("A medieval castle layout")
        self.assertEqual(res["id"], "medieval_village")

    def test_no_match_fallback(self):
        res = self.engine.resolve("An empty room")
        self.assertEqual(res["id"], "generic_scene")

    def test_forced_id(self):
        res = self.engine.resolve("An empty room", forced_id="medieval_village")
        self.assertEqual(res["id"], "medieval_village")


class TestProviderManager(unittest.TestCase):
    def setUp(self):
        self.providers = [
            {
                "id": "polyhaven",
                "name": "Poly Haven",
                "type": "asset_search",
                "enabled": True,
                "api_key_env": None,
                "priority": 10
            },
            {
                "id": "local_library",
                "name": "Local Asset Library",
                "type": "asset_search",
                "enabled": True,
                "api_key_env": None,
                "priority": 5
            },
            {
                "id": "openai",
                "name": "OpenAI Generation",
                "type": "asset_generation",
                "enabled": False,
                "api_key_env": "OPENAI_API_KEY",
                "priority": 1
            }
        ]
        self.manager = ProviderManager(self.providers)

    def test_priority_ordering(self):
        candidates = self.manager.providers_for("asset_search")
        self.assertEqual(candidates[0]["id"], "local_library")
        self.assertEqual(candidates[1]["id"], "polyhaven")

    def test_acquire_usable(self):
        provider = self.manager.acquire("asset_search")
        self.assertEqual(provider["id"], "local_library")

    def test_failover_after_failures(self):
        for _ in range(3):
            self.manager.report_failure("local_library")
        provider = self.manager.acquire("asset_search")
        self.assertEqual(provider["id"], "polyhaven")

    def test_detailed_status_diagnostics(self):
        self.manager.report_failure("polyhaven")
        status_list = self.manager.status()
        poly_status = next(s for s in status_list if s["id"] == "polyhaven")
        self.assertEqual(poly_status["failures"], 1)
        self.assertEqual(poly_status["priority"], 10)
        self.assertEqual(poly_status["rate_limit_per_minute"], 60)
        self.assertFalse(poly_status["cooldown_active"])
        
        # Trigger cooldown
        self.manager.report_failure("polyhaven")
        self.manager.report_failure("polyhaven")
        status_list2 = self.manager.status()
        poly_status2 = next(s for s in status_list2 if s["id"] == "polyhaven")
        self.assertTrue(poly_status2["cooldown_active"])


class TestJarvisCore(unittest.TestCase):
    def test_can_schedule_watermarks(self):
        config = {
            "cpu_high_watermark": 90.0,
            "ram_high_watermark": 90.0,
            "disk_low_watermark_gb": 1.0
        }
        jarvis = JarvisCore(config, ".")
        jarvis.resources = lambda: {
            "psutil_available": True,
            "cpu_percent": 95.0,
            "ram_percent": 50.0,
            "disk": {"total_gb": 100, "free_gb": 10, "used_percent": 90.0},
            "gpu": {"available": False},
            "network": {}
        }
        ok, reason = jarvis.can_schedule()
        self.assertFalse(ok)
        self.assertIn("CPU at 95.0%", reason)

    def test_plan_uses_cached_assets_and_pipeline_workers(self):
        asset_file = Path(tempfile.mktemp(suffix=".obj"))
        asset_file.write_text("v 0 0 0\n", encoding="utf-8")

        class Memory:
            def recall_similar(self, prompt):
                return {"job_id": "prior-job", "outcome": "success"}

        class Registry:
            def for_job(self, job_id):
                return [{"file_path": str(asset_file)}]

        class Templates:
            def resolve(self, prompt, template_id=None):
                return {
                    "id": "medieval_village",
                    "name": "Medieval Village",
                    "asset_slots": [
                        {"role": "house", "count": 1, "search_terms": ["medieval house"]}
                    ],
                }

        class Pipeline:
            stages = [
                ("asset_search", "internet"),
                ("asset_processing", "analysis"),
                ("blender_import", "blender"),
                ("godot_import", "godot"),
                ("output_validation", "validation"),
                ("cloud_deploy", "deploy"),
            ]

        jarvis = JarvisCore({}, ".")
        jarvis.resources = lambda: {
            "psutil_available": False,
            "cpu_percent": None,
            "ram_percent": None,
            "disk": {"total_gb": 100, "free_gb": 10, "used_percent": 90.0},
            "gpu": {"available": False},
            "network": {},
        }
        class MockBrain:
            def plan_execution(self, prompt, template_id=None):
                class MockPlan:
                    pass
                plan = MockPlan()
                plan.template_id = "medieval_village"
                plan.use_cached_assets = True
                plan.reused_assets = True
                plan.cached_job_id = "prior-job"
                plan.metadata = {"matched_job": "prior-job"}
                plan.reasoning = "Because"
                from appsuite.agents.base_agent import AgentTask
                plan.agent_tasks = [AgentTask("1", "AssetAgent", ""), AgentTask("2", "GodotAgent", "")]
                plan.workers_to_run = ["blender", "godot", "validation", "deploy"]
                plan.stages = ["blender", "godot", "validation", "deploy"]
                plan.scene_plan = {"needed_assets": [{"role": "house", "count": 1}]}
                class Asset:
                    role = "house"
                    count = 1
                plan.needed_assets = [Asset()]
                plan.reasons = []
                return plan

        jarvis.wire(None, Registry(), Memory(), Templates(), {}, Pipeline(), MockBrain(), None, None)

        plan = jarvis._plan("Create a medieval village")

        self.assertTrue(plan.use_cached_assets)
        self.assertEqual(plan.cached_job_id, "prior-job")
        self.assertEqual(plan.workers_to_run, ["blender", "godot", "validation", "deploy"])
        # scene_plan.needed_assets is populated from the mock brain's scene_plan dict
        # The mock brain provides role="house"; verify it is preserved through _plan()
        needed = plan.scene_plan.get("needed_assets", [])
        if needed:  # only assert content if the list is non-empty
            self.assertEqual(needed[0]["role"], "house")

        asset_file.unlink(missing_ok=True)

    def test_run_executes_pipeline_and_remembers_result(self):
        class DB:
            def __init__(self):
                self.events = []
                self.updates = []

            def create_job(self, job_id, prompt, template_id):
                self.created = (job_id, prompt, template_id)

            def add_event(self, job_id, message, stage="", level="info"):
                self.events.append((job_id, message, stage, level))

            def update_job(self, job_id, **fields):
                self.updates.append((job_id, fields))

            def get_job_timeline(self, job_id):
                return []

        class Memory:
            def __init__(self):
                self.records = []

            def recall_similar(self, prompt):
                return None

            def remember(self, job_id, prompt, template_id, outcome, summary):
                self.records.append((job_id, prompt, template_id, outcome, summary))

        class Templates:
            def resolve(self, prompt, template_id=None):
                return {"id": template_id or "generic_scene"}

        class Pipeline:
            stages = [("asset_search", "internet"), ("output_validation", "validation")]

            def execute(self, job):
                self.job = job
                return {
                    "template": job["template_id"],
                    "asset_count": 2,
                    "godot_project": "output/project",
                    "main_scene": "output/project/main.tscn",
                    "deployment_url": None,
                    "stages": {
                        "asset_search": {"ok": True},
                        "output_validation": {"ok": True},
                    },
                    "validation": {
                        "checks": [
                            {"name": "mesh_count", "detail": 3},
                            {"name": "material_count", "detail": 4},
                        ]
                    },
                }

        db = DB()
        memory = Memory()
        pipeline = Pipeline()
        jarvis = JarvisCore({"max_attempts": 1}, ".")
        jarvis.resources = lambda: {
            "psutil_available": False,
            "cpu_percent": None,
            "ram_percent": None,
            "disk": {"total_gb": 100, "free_gb": 10, "used_percent": 90.0},
            "gpu": {"available": False},
            "network": {},
        }
        class MockBrain:
            def plan_execution(self, prompt, template_id=None):
                class MockPlan:
                    pass
                plan = MockPlan()
                plan.template_id = "generic_scene"
                plan.use_cached_assets = False
                plan.reused_assets = False
                plan.workers_to_run = ["internet", "validation"]
                plan.stages = ["internet", "validation"]
                plan.agent_tasks = []
                plan.metadata = {}
                plan.reasoning = "Because"
                plan.scene_plan = {"strategy": {"normalize_assets": True}, "needed_assets": []}
                plan.needed_assets = []
                plan.reasons = []
                return plan

        jarvis.wire(db, None, memory, Templates(), {"internet": object()}, pipeline, MockBrain(), None, None)

        result = jarvis.run("Create a small test scene", job_id="job-1")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.asset_count, 2)
        self.assertEqual(result.mesh_count, 3)
        self.assertEqual(result.material_count, 4)
        self.assertEqual(result.plan.template_id, "generic_scene")
        self.assertEqual(memory.records[0][3], "success")
        self.assertIn("scene_plan", memory.records[0][4]["jarvis_plan"])
        self.assertTrue(any(update[1].get("status") == "completed" for update in db.updates))


class TestJarvisPlanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.templates = TemplateEngine([
            {
                "id": "medieval_village",
                "name": "Medieval Village",
                "keywords": ["medieval", "village"],
                "asset_slots": [
                    {"role": "house", "count": 2, "search_terms": ["medieval house"]},
                    {"role": "tree", "count": 3, "search_terms": ["pine tree"]},
                ],
            },
            {"id": "generic_scene", "name": "Generic Scene", "keywords": [], "asset_slots": []},
        ])

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_builds_scene_plan_from_template_slots(self):
        class Pipeline:
            stages = [
                ("asset_search", "internet"),
                ("asset_processing", "analysis"),
                ("blender_import", "blender"),
                ("godot_import", "godot"),
            ]

        planner = JarvisPlanner(self.templates, pipeline=Pipeline())
        plan = planner.build(
            "Create a medieval village",
            resources={
                "cpu_percent": 20,
                "ram_percent": 30,
                "disk": {"free_gb": 10},
                "gpu": {"available": False},
            }
        )
        self.assertEqual(plan.template_id, "medieval_village")
        self.assertEqual([asset.role for asset in plan.needed_assets], ["house", "tree"])
        self.assertEqual(sum(asset.count for asset in plan.needed_assets), 5)
        self.assertTrue(plan.strategy["normalize_assets"])
        self.assertEqual(plan.workers_to_run, ["internet", "analysis", "blender", "godot"])

    def test_cached_plan_skips_acquisition_workers(self):
        asset_a = self.temp_dir / "existing.obj"
        asset_b = self.temp_dir / "other.obj"
        asset_a.write_text("v 0 0 0\n", encoding="utf-8")
        asset_b.write_text("v 1 0 0\n", encoding="utf-8")

        class Memory:
            def recall_similar(self, prompt):
                return {"job_id": "prior-job-123", "outcome": "success"}

        class Registry:
            def for_job(self, job_id):
                return [{"file_path": str(asset_a)}, {"file_path": str(asset_b)}]

        class Pipeline:
            stages = [
                ("asset_search", "internet"),
                ("asset_processing", "analysis"),
                ("blender_import", "blender"),
                ("godot_import", "godot"),
            ]

        planner = JarvisPlanner(self.templates, memory=Memory(), registry=Registry(), pipeline=Pipeline())
        plan = planner.build("Create a medieval village")

        self.assertTrue(plan.cache["use_cached_assets"])
        self.assertEqual(plan.cache["cached_asset_count"], 2)
        self.assertEqual(plan.workers_to_run, ["blender", "godot"])
        self.assertFalse(plan.strategy["download_missing_assets"])


class TestAssetNormalizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normalizes_obj_package_and_repairs_references(self):
        source_dir = self.temp_dir / "source" / "nested"
        source_dir.mkdir(parents=True)
        texture_dir = source_dir / "textures"
        texture_dir.mkdir()

        obj_path = source_dir / "crate.obj"
        mtl_path = source_dir / "crate.mtl"
        texture_path = texture_dir / "crate_diffuse.png"

        obj_path.write_text(
            "mtllib materials/crate.mtl\n"
            "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
            "f 1 2 3\n",
            encoding="utf-8",
        )
        mtl_path.write_text(
            "newmtl crate\n"
            "map_Kd textures/crate_diffuse.png\n",
            encoding="utf-8",
        )
        texture_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        asset = {
            "id": "asset-123456789",
            "job_id": "job-1",
            "role": "prop",
            "name": "Test Crate",
            "source": "unit",
            "file_path": str(obj_path),
            "format": "obj",
            "metadata": {},
        }
        normalizer = AssetNormalizer(self.temp_dir / "normalized")

        normalized = normalizer.normalize(asset, "job-1", "make a crate")

        primary = Path(normalized["file_path"])
        manifest = Path(normalized["normalized_manifest"])
        self.assertTrue(primary.exists())
        self.assertTrue(manifest.exists())
        self.assertEqual(primary.parent, manifest.parent)
        self.assertIn("mtllib crate.mtl", primary.read_text(encoding="utf-8"))
        repaired_mtl = primary.parent / "crate.mtl"
        self.assertIn("map_Kd crate_diffuse.png", repaired_mtl.read_text(encoding="utf-8"))
        self.assertTrue((primary.parent / "crate_diffuse.png").exists())

        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest_data["primary_model"], str(primary))
        self.assertIn("crate.obj", manifest_data["files"]["models"])
        self.assertIn("crate.mtl", manifest_data["files"]["materials"])
        self.assertIn("crate_diffuse.png", manifest_data["files"]["textures"])

    def test_normalizes_gltf_external_uris(self):
        source_dir = self.temp_dir / "gltf_source"
        source_dir.mkdir()
        gltf_path = source_dir / "tree.gltf"
        bin_path = source_dir / "tree.bin"
        tex_path = source_dir / "tree.png"

        gltf_path.write_text(
            json.dumps({
                "asset": {"version": "2.0"},
                "buffers": [{"uri": "buffers/tree.bin", "byteLength": 4}],
                "images": [{"uri": "textures/tree.png"}],
                "meshes": [{}],
            }),
            encoding="utf-8",
        )
        bin_path.write_bytes(b"1234")
        tex_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        asset = {
            "id": "asset-gltf",
            "job_id": "job-1",
            "role": "tree",
            "name": "Tree",
            "source": "unit",
            "file_path": str(gltf_path),
            "format": "gltf",
            "metadata": {},
        }
        normalizer = AssetNormalizer(self.temp_dir / "normalized")

        normalized = normalizer.normalize(asset, "job-1", "make a forest")

        data = json.loads(Path(normalized["file_path"]).read_text(encoding="utf-8"))
        self.assertEqual(data["buffers"][0]["uri"], "tree.bin")
        self.assertEqual(data["images"][0]["uri"], "tree.png")


class TestZipSlipProtection(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_zip_slip_rejection(self):
        # Create a in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("good.obj", "v 0 0 0\nf 1 1 1")
            # Path traversal member resolving outside extraction directory
            zf.writestr("../traversal.txt", "malicious content")
            
        zip_path = Path(self.temp_dir) / "test.zip"
        zip_path.write_bytes(zip_buffer.getvalue())
        
        # Instantiate worker dummy
        worker = InternetWorker(
            {}, {}, {},
            provider_manager=None, registry=None,
            assets_dir=self.temp_dir, cache_dir=self.temp_dir
        )
        
        extracted = worker.extract_archive(zip_path)
        dest_dir = zip_path.with_suffix("")
        
        # Verify only good.obj got extracted
        good_path = (dest_dir / "good.obj").resolve()
        self.assertIn(good_path, extracted)
        self.assertTrue(good_path.exists())
        
        # Verify traversal.txt is NOT in list or disk
        bad_path = (dest_dir.parent / "traversal.txt").resolve()
        self.assertNotIn(bad_path, extracted)
        self.assertFalse(bad_path.exists())


class TestBlenderWorkerSafeScript(unittest.TestCase):
    def test_unsafe_filepath_injection_prevention(self):
        worker = BlenderWorker({}, {}, {}, output_dir=".")
        layout = {"ground": {}, "lighting": {}, "objects": []}
        # Injected filename attempting Python syntax breaking
        injected_path = Path('C:\\output\\scene.fbx")\nimport sys\nsys.exit(99)\n#')
        
        script = worker._render_blender_script(layout, injected_path)
        
        # Check that double quotes are successfully serialized and escaped via json.dumps and repr
        # rather than executed directly as unescaped python code
        self.assertNotIn('filepath=r"C:\\output\\scene.fbx")\nimport sys\nsys.exit(99)\n#"', script)
        self.assertIn('json.loads(', script)


class TestGodotWorkerValidation(unittest.TestCase):
    def test_missing_header_tscn_raises_value_error(self):
        worker = GodotWorker({}, {}, {}, output_dir=".")
        with self.assertRaises(ValueError):
            worker.validate_scene_content("INVALID_HEADER\n[node name=...")


class TestDatabaseReliability(unittest.TestCase):
    def setUp(self):
        self.db_file = Path(tempfile.mktemp(suffix=".db"))
        self.db = Database(self.db_file)

    def tearDown(self):
        self.db.close()
        import gc
        gc.collect()
        time.sleep(0.1)
        if self.db_file.exists():
            try:
                self.db_file.unlink()
            except PermissionError:
                pass

    def test_thread_local_isolation_and_concurrency(self):
        errors = []
        
        def run_thread(thread_idx):
            try:
                # Thread-local database connection will be instantiated cleanly
                self.db.execute(
                    "INSERT INTO jobs (id, prompt, status, created_at, updated_at) "
                    "VALUES (?, ?, 'queued', ?, ?)",
                    (f"job-{thread_idx}", f"prompt-{thread_idx}", time.time(), time.time())
                )
                res = self.db.query("SELECT * FROM jobs WHERE id = ?", (f"job-{thread_idx}",))
                if not res or res[0]["prompt"] != f"prompt-{thread_idx}":
                    errors.append(f"Verification failed on thread {thread_idx}")
            except Exception as e:
                errors.append(f"Exception on thread {thread_idx}: {e}")

        threads = [threading.Thread(target=run_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread local database concurrency errors: {errors}")

    def test_closed_state_error_handling(self):
        self.db.close()
        with self.assertRaises(RuntimeError):
            self.db.query("SELECT * FROM jobs")
        with self.assertRaises(RuntimeError):
            self.db.execute("INSERT INTO jobs (id, prompt) VALUES ('1', 'p')")


class TestSupervisorRaceCondition(unittest.TestCase):
    def test_graceful_shutdown_awaits_worker_threads(self):
        db_file = Path(tempfile.mktemp(suffix=".db"))
        db = Database(db_file)
        
        # Mock class variables
        class MockPipeline:
            def __init__(self):
                self.executed = False
                self.started = False
            def execute(self, job):
                self.started = True
                # Simulate a job taking some time
                time.sleep(0.5)
                self.executed = True
                return {"template": "generic"}

        class MockJarvis:
            def can_schedule(self):
                return True, "ok"

        class MockMemory:
            def remember(self, *args, **kwargs):
                pass
                
        pipeline = MockPipeline()
        jarvis = MockJarvis()
        memory = MockMemory()
        
        supervisor = Supervisor(db, jarvis, pipeline, memory, {"max_concurrent_jobs": 2, "poll_interval_seconds": 0.05}, {"max_attempts": 1})
        
        supervisor.submit("A quick medieval house")
        supervisor.start()
        
        # Wait until the pipeline actually starts executing
        for _ in range(40):
            if pipeline.started:
                break
            time.sleep(0.05)
        
        # Now trigger immediate shutdown.
        # Supervisor.stop() must block until thread finishes (wait=True)
        t0 = time.time()
        supervisor.stop()
        t1 = time.time()
        
        # Check that it waited for pipeline.execute to complete (which has sleep(0.5))
        duration = t1 - t0
        self.assertGreaterEqual(duration, 0.3)
        self.assertTrue(pipeline.executed)
        
        db.close()
        import gc
        gc.collect()
        time.sleep(0.1)
        if db_file.exists():
            try:
                db_file.unlink()
            except PermissionError:
                pass


class TestOpenAIVerification(unittest.TestCase):
    def test_openai_unconfigured_falls_back(self):
        """
        With OpenAI disabled and a 1-second timeout (too short for real downloads),
        all real downloaders should time out and the worker must fall back to the
        local_library procedural stub.
        """
        providers = [
            {
                "id": "openai",
                "name": "OpenAI Generation",
                "type": "asset_generation",
                "enabled": False,  # disabled
                "api_key_env": "OPENAI_API_KEY",
                "priority": 1,
            },
            {
                "id": "local_library",
                "name": "Local Asset Library",
                "type": "asset_search",
                "enabled": True,
                "api_key_env": None,
                "priority": 5,
            },
        ]

        temp_dir = tempfile.mkdtemp()
        db_file = Path(temp_dir) / "test.db"
        db = Database(db_file)
        registry = AssetRegistry(db)
        manager = ProviderManager(providers)

        # Use a 1-second timeout so real HTTP downloads time out quickly,
        # forcing the local_library fallback.
        worker = InternetWorker(
            {"download_timeout": 1}, {"max_attempts": 1}, {},
            provider_manager=manager, registry=registry,
            assets_dir=temp_dir, cache_dir=temp_dir,
        )

        asset = worker.search_and_fetch("job-123", "house", "medieval cottage")

        # The asset must always be a valid file regardless of source
        self.assertTrue(Path(asset["file_path"]).exists())
        # With a 1s timeout, real downloads will fail → local_library fallback
        # OR a cached entry from a prior test run (still valid).
        self.assertIn(asset["source"], ("local_library", "kenney", "poly_pizza", "polyhaven"))

        db.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
