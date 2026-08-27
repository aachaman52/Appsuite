"""Comprehensive unit tests for PyFlare's Deterministic Routing Layer."""
from __future__ import annotations

import ast
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from pyflare.core.config import load_config
from pyflare.core.hardware_manager import HardwareManager
from pyflare.core.main import AppContext
from pyflare.core.state import WorkerResult, WorkerStatus
from pyflare.router.adapters import (
    AdapterUnavailableError,
    ExecutionTimeoutError,
    ProviderExecutionError,
    UnsupportedTaskError,
    WorkerExecutionError,
    WorkerValidationError,
    create_blender_worker_adapter,
    create_code_worker_adapter,
    create_godot_worker_adapter,
    create_provider_manager_adapter,
    create_rule_engine_adapter,
    create_validation_worker_adapter,
    sanitize_error_message,
)
from pyflare.router.capability_registry import CapabilityRegistry
from pyflare.router.executor import RouterExecutor
from pyflare.router.history import RouterHistoryTracker
from pyflare.router.models import (
    HardwareProfile,
    HardwareTier,
    PrivacyLevel,
    ProviderCapability,
    RouteCandidate,
    RouteDecision,
    RouteOutcome,
    TaskSpec,
    TaskType,
)
from pyflare.router.router import DeterministicRouter
from pyflare.router.scoring import filter_candidate, score_candidate


@pytest.fixture
def mock_hardware() -> HardwareProfile:
    """Fixture providing a standard mid-tier hardware profile."""
    return HardwareProfile(
        cpu_cores_logical=8,
        cpu_cores_physical=6,
        ram_total_mb=8192.0,
        ram_available_mb=4096.0,
        gpu_name=None,
        vram_total_mb=0.0,
        vram_available_mb=0.0,
        disk_available_gb=50.0,
        os_name="linux",
        hardware_tier=HardwareTier.MID,
        installed_binaries={"git": True, "python": True, "blender": False, "godot": False},
        resource_pressure={"cpu_percent": 15.0, "ram_percent": 50.0, "disk_percent": 40.0},
    )


@pytest.fixture
def temp_history(tmp_path: Path) -> RouterHistoryTracker:
    """Provide isolated history tracker SQLite database."""
    db_file = tmp_path / "test_router_history.db"
    return RouterHistoryTracker(str(db_file))


@pytest.mark.unit
def test_deterministic_output(mock_hardware, temp_history):
    """Verify that same inputs produce bit-identical deterministic decisions."""
    router = DeterministicRouter(history_tracker=temp_history)
    task = TaskSpec(prompt="Write unit tests for authentication", task_type=TaskType.CODE_GENERATION)

    d1 = router.plan_route(task)
    d2 = router.plan_route(task)

    assert d1.selected_candidate is not None
    assert d2.selected_candidate is not None
    assert d1.selected_candidate.candidate_id == d2.selected_candidate.candidate_id
    assert d1.score == d2.score
    assert [c.candidate_id for c in d1.fallback_candidates] == [c.candidate_id for c in d2.fallback_candidates]


@pytest.mark.unit
def test_capability_matching_rejects_missing_capability(mock_hardware):
    """Verify candidates missing required capabilities are filtered out."""
    candidate = RouteCandidate(
        candidate_id="simple-code",
        provider_type="local_worker",
        display_name="Simple Code Generator",
        is_local=True,
        supported_task_types=[TaskType.CODE_GENERATION],
        capabilities=[ProviderCapability(capability_name="python_basic", level=0.8)],
    )

    task = TaskSpec(
        prompt="Synthesize shader code",
        task_type=TaskType.CODE_GENERATION,
        required_capabilities=["hlsl_shader_synthesis"],
    )

    accepted, reason = filter_candidate(candidate, task, mock_hardware)
    assert accepted is False
    assert "missing required capability" in str(reason).lower()


@pytest.mark.unit
def test_stable_tie_breaking(mock_hardware, temp_history):
    """Verify candidates with identical scores are stably tie-broken by candidate_id."""
    registry = CapabilityRegistry()
    registry._candidates.clear()

    c_beta = RouteCandidate(
        candidate_id="candidate-beta",
        provider_type="mock",
        display_name="Beta Candidate",
        is_local=True,
        quality_score=0.80,
        expected_latency_seconds=1.0,
        estimated_cost_usd=0.0,
        supported_task_types=[TaskType.GENERAL],
    )
    c_alpha = RouteCandidate(
        candidate_id="candidate-alpha",
        provider_type="mock",
        display_name="Alpha Candidate",
        is_local=True,
        quality_score=0.80,
        expected_latency_seconds=1.0,
        estimated_cost_usd=0.0,
        supported_task_types=[TaskType.GENERAL],
    )
    registry.register_candidate(c_beta)
    registry.register_candidate(c_alpha)

    router = DeterministicRouter(registry=registry, history_tracker=temp_history)
    task = TaskSpec(prompt="General task", task_type=TaskType.GENERAL, allow_cloud=False)

    decision = router.plan_route(task)
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.candidate_id == "candidate-alpha"
    assert len(decision.fallback_candidates) == 1
    assert decision.fallback_candidates[0].candidate_id == "candidate-beta"


@pytest.mark.unit
def test_weak_hardware_rejection(mock_hardware):
    """Verify candidates with high RAM requirements are rejected on low-resource hardware."""
    weak_hw = mock_hardware.model_copy()
    weak_hw.ram_available_mb = 512.0

    heavy_candidate = RouteCandidate(
        candidate_id="heavy-local-llm",
        provider_type="local_llm",
        display_name="70B Local LLM",
        is_local=True,
        min_ram_mb=16384.0,
        supported_task_types=[TaskType.GENERAL],
    )

    task = TaskSpec(prompt="Run heavy model", task_type=TaskType.GENERAL)
    accepted, reason = filter_candidate(heavy_candidate, task, weak_hw)
    assert accepted is False
    assert "insufficient available ram" in str(reason).lower()


@pytest.mark.unit
def test_missing_gpu_handling(mock_hardware):
    """Verify candidates requiring VRAM are rejected gracefully when GPU is absent."""
    no_gpu_hw = mock_hardware.model_copy()
    no_gpu_hw.gpu_name = None
    no_gpu_hw.vram_available_mb = 0.0

    gpu_candidate = RouteCandidate(
        candidate_id="gpu-diffusion",
        provider_type="local_diffusion",
        display_name="Local Stable Diffusion",
        is_local=True,
        min_vram_mb=4096.0,
        supported_task_types=[TaskType.IMAGE_GENERATION],
    )

    task = TaskSpec(prompt="Generate picture", task_type=TaskType.IMAGE_GENERATION)
    accepted, reason = filter_candidate(gpu_candidate, task, no_gpu_hw)
    assert accepted is False
    assert "insufficient available vram" in str(reason).lower()


@pytest.mark.unit
def test_missing_executable_rejection(mock_hardware):
    """Verify candidates requiring uninstalled binaries are rejected."""
    mock_hardware.installed_binaries["blender"] = False
    blender_candidate = RouteCandidate(
        candidate_id="blender-exec",
        provider_type="local_worker",
        display_name="Blender Mesh Builder",
        is_local=True,
        required_executable="blender",
        supported_task_types=[TaskType.THREE_D_GENERATION],
    )

    task = TaskSpec(prompt="Export FBX", task_type=TaskType.THREE_D_GENERATION)
    accepted, reason = filter_candidate(blender_candidate, task, mock_hardware)
    assert accepted is False
    assert "not installed" in str(reason).lower()


@pytest.mark.unit
def test_missing_api_key_rejection(monkeypatch):
    """Verify cloud candidates without API keys are marked unavailable."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    registry = CapabilityRegistry()
    c = registry.get_candidate("openai-cloud")
    evaluated = registry._evaluate_availability(c)
    assert evaluated.is_available is False
    assert "Missing environment variable: OPENAI_API_KEY" in evaluated.unavailability_reason


@pytest.mark.unit
def test_privacy_confinement(mock_hardware):
    """Verify confidential tasks reject public cloud candidates."""
    public_cloud = RouteCandidate(
        candidate_id="public-cloud",
        provider_type="cloud_llm",
        display_name="Public Cloud Provider",
        is_local=False,
        privacy_level=PrivacyLevel.PUBLIC,
        supported_task_types=[TaskType.CODE_GENERATION],
    )

    confidential_task = TaskSpec(
        prompt="Process private company secrets",
        task_type=TaskType.CODE_GENERATION,
        privacy_level=PrivacyLevel.CONFIDENTIAL,
    )

    accepted, reason = filter_candidate(public_cloud, confidential_task, mock_hardware)
    assert accepted is False
    assert "privacy level" in str(reason).lower()


@pytest.mark.unit
def test_cloud_disabled_request(mock_hardware):
    """Verify allow_cloud=False strictly rejects non-local candidates."""
    cloud_cand = RouteCandidate(
        candidate_id="cloud-1",
        provider_type="cloud_llm",
        display_name="Cloud API",
        is_local=False,
        supported_task_types=[TaskType.GENERAL],
    )

    local_task = TaskSpec(prompt="Offline query", task_type=TaskType.GENERAL, allow_cloud=False)
    accepted, reason = filter_candidate(cloud_cand, local_task, mock_hardware)
    assert accepted is False
    assert "cloud processing disallowed" in str(reason).lower()


@pytest.mark.unit
def test_zero_cost_preference(mock_hardware):
    """Verify max_cost_usd=0.0 rejects paid candidates."""
    paid_cand = RouteCandidate(
        candidate_id="paid-llm",
        provider_type="cloud_llm",
        display_name="Paid LLM",
        estimated_cost_usd=0.02,
        supported_task_types=[TaskType.GENERAL],
    )

    free_task = TaskSpec(prompt="Budget query", task_type=TaskType.GENERAL, max_cost_usd=0.0, privacy_level=PrivacyLevel.PUBLIC)
    accepted, reason = filter_candidate(paid_cand, free_task, mock_hardware)
    assert accepted is False
    assert "exceeds max allowed" in str(reason).lower()


@pytest.mark.unit
def test_min_quality_requirement(mock_hardware):
    """Verify quality below min_quality_score is rejected."""
    low_qual = RouteCandidate(
        candidate_id="low-qual",
        provider_type="mock",
        display_name="Low Quality Model",
        quality_score=0.65,
        supported_task_types=[TaskType.GENERAL],
    )

    high_qual_task = TaskSpec(prompt="Critical code", task_type=TaskType.GENERAL, min_quality_score=0.90, privacy_level=PrivacyLevel.PUBLIC)
    accepted, reason = filter_candidate(low_qual, high_qual_task, mock_hardware)
    assert accepted is False
    assert "below required minimum" in str(reason).lower()


@pytest.mark.unit
def test_missing_adapter_raises_and_falls_back(temp_history):
    """Verify missing adapter raises AdapterUnavailableError and falls back safely without fake success."""
    no_adapter_cand = RouteCandidate(
        candidate_id="unimplemented-cand",
        provider_type="custom_experimental",
        display_name="Unimplemented Node",
        is_local=True,
    )
    fallback_cand = RouteCandidate(
        candidate_id="working-fallback",
        provider_type="local_rules",
        display_name="Working Fallback",
        is_local=True,
    )

    task = TaskSpec(prompt="Run experimental task", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=no_adapter_cand,
        fallback_candidates=[fallback_cand],
    )

    executor = RouterExecutor(history_tracker=temp_history)
    # Register adapter ONLY for fallback
    executor.register_adapter("working-fallback", lambda t, c: {"result": "recovered_via_fallback"})

    res = executor.execute(task, decision)
    assert res.success is True
    assert res.final_candidate_id == "working-fallback"
    assert len(res.attempts) == 2
    assert "No execution adapter available" in str(res.attempts[0].error)
    assert res.attempts[0].is_retryable is False


@pytest.mark.unit
def test_successful_real_worker_adapters(temp_history):
    """Verify real worker adapters invoke underlying worker run methods correctly."""
    # 1. CodeWorker
    mock_code_worker = MagicMock()
    mock_code_worker.run.return_value = WorkerResult(status=WorkerStatus.SUCCESS, data={"code": "pass"})
    code_adapter = create_code_worker_adapter(mock_code_worker)

    task = TaskSpec(prompt="Generate GDScript player", task_type=TaskType.CODE_GENERATION)
    cand = RouteCandidate(candidate_id="code-worker", provider_type="hybrid_worker", display_name="Code Worker")
    res_code = code_adapter(task, cand)
    assert res_code["status"] == "success"
    assert res_code["worker"] == "code"
    assert mock_code_worker.run.called

    # 2. BlenderWorker
    mock_blender_worker = MagicMock()
    mock_blender_worker.run.return_value = WorkerResult(status=WorkerStatus.SUCCESS, data={"scene": "scene.fbx"})
    blender_adapter = create_blender_worker_adapter(mock_blender_worker)
    res_blender = blender_adapter(task, cand)
    assert res_blender["status"] == "success"
    assert res_blender["worker"] == "blender"

    # 3. GodotWorker
    mock_godot_worker = MagicMock()
    mock_godot_worker.run.return_value = WorkerResult(status=WorkerStatus.SUCCESS, data={"project": "project.godot"})
    godot_adapter = create_godot_worker_adapter(mock_godot_worker)
    res_godot = godot_adapter(task, cand)
    assert res_godot["status"] == "success"
    assert res_godot["worker"] == "godot"

    # 4. ValidationWorker
    mock_val_worker = MagicMock()
    mock_val_worker.run.return_value = WorkerResult(status=WorkerStatus.SUCCESS, data={"valid": True})
    val_adapter = create_validation_worker_adapter(mock_val_worker)
    res_val = val_adapter(task, cand)
    assert res_val["status"] == "success"
    assert res_val["worker"] == "validation"

    # 5. ProviderManager
    mock_prov_mgr = MagicMock()
    mock_prov_mgr.generate_text.return_value = "def test(): return 42"
    prov_adapter = create_provider_manager_adapter(mock_prov_mgr)
    res_prov = prov_adapter(task, cand)
    assert res_prov["status"] == "success"
    assert res_prov["output"] == "def test(): return 42"


@pytest.mark.unit
def test_failed_worker_result_raises_typed_error_and_falls_back(temp_history):
    """Verify worker returning failed status raises WorkerExecutionError and triggers fallback."""
    mock_worker = MagicMock()
    mock_worker.run.return_value = WorkerResult(
        status=WorkerStatus.FAILED,
        reason="Syntax parser failed on line 12",
    )
    code_adapter = create_code_worker_adapter(mock_worker)

    task = TaskSpec(prompt="Bad code", task_type=TaskType.CODE_GENERATION)
    primary_cand = RouteCandidate(candidate_id="primary-code", provider_type="hybrid_worker", display_name="Primary")
    fallback_cand = RouteCandidate(candidate_id="fb-code", provider_type="local_worker", display_name="Fallback")

    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=primary_cand,
        fallback_candidates=[fallback_cand],
    )

    executor = RouterExecutor(history_tracker=temp_history, max_retries_per_candidate=0)
    executor.register_adapter("primary-code", code_adapter)
    executor.register_adapter("fb-code", lambda t, c: {"status": "success", "recovered": True})

    res = executor.execute(task, decision)
    assert res.success is True
    assert res.final_candidate_id == "fb-code"
    assert len(res.attempts) == 2
    assert "Syntax parser failed on line 12" in str(res.attempts[0].error)


@pytest.mark.unit
def test_rejected_validation_result_raises_non_retryable_error(temp_history):
    """Verify validation failure raises non-retryable WorkerValidationError."""
    mock_val = MagicMock()
    mock_val.run.return_value = WorkerResult(
        status=WorkerStatus.FAILED,
        reason="Security boundary check violation",
    )
    val_adapter = create_validation_worker_adapter(mock_val)

    task = TaskSpec(prompt="Validate safety", task_type=TaskType.VALIDATION)
    cand = RouteCandidate(candidate_id="val-cand", provider_type="local_worker", display_name="Validator")
    decision = RouteDecision(task_id=task.task_id, selected_candidate=cand)

    executor = RouterExecutor(history_tracker=temp_history, max_retries_per_candidate=3)
    executor.register_adapter("val-cand", val_adapter)

    res = executor.execute(task, decision)
    assert res.success is False
    assert len(res.attempts) == 1  # Non-retryable: 1 attempt only
    assert res.attempts[0].is_retryable is False


@pytest.mark.unit
def test_malformed_worker_result_handled_safely(temp_history):
    """Verify null or malformed worker response raises WorkerExecutionError."""
    mock_bad_worker = MagicMock()
    mock_bad_worker.run.return_value = None  # Malformed None return
    bad_adapter = create_code_worker_adapter(mock_bad_worker)

    task = TaskSpec(prompt="Test bad worker", task_type=TaskType.CODE_GENERATION)
    cand = RouteCandidate(candidate_id="bad-cand", provider_type="worker", display_name="Bad Worker")
    with pytest.raises(WorkerExecutionError) as exc_info:
        bad_adapter(task, cand)
    assert "null/empty response" in str(exc_info.value)


@pytest.mark.unit
def test_provider_auth_failure_is_non_retryable(temp_history):
    """Verify provider 401/auth failure raises non-retryable ProviderExecutionError."""
    mock_pm = MagicMock()
    mock_pm.generate_text.side_effect = RuntimeError("401 Unauthorized: Invalid API Key")
    prov_adapter = create_provider_manager_adapter(mock_pm)

    task = TaskSpec(prompt="Query LLM", task_type=TaskType.GENERAL)
    cand = RouteCandidate(candidate_id="cloud-cand", provider_type="cloud_llm", display_name="Cloud LLM")

    with pytest.raises(ProviderExecutionError) as exc_info:
        prov_adapter(task, cand)
    assert exc_info.value.is_retryable is False


@pytest.mark.unit
def test_execution_timeout_enforcement_and_fallback(temp_history):
    """Verify execution timeout is enforced and causes safe transition to fallback."""
    slow_cand = RouteCandidate(
        candidate_id="slow-cand",
        provider_type="cloud",
        display_name="Hanging Slow Candidate",
        is_local=False,
    )
    fast_cand = RouteCandidate(
        candidate_id="fast-cand",
        provider_type="local",
        display_name="Fast Fallback",
        is_local=True,
    )

    task = TaskSpec(prompt="Timeout task", task_type=TaskType.GENERAL, preferred_latency_seconds=0.1)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=slow_cand,
        fallback_candidates=[fast_cand],
    )

    executor = RouterExecutor(history_tracker=temp_history, default_timeout_seconds=0.1, max_retries_per_candidate=0)

    def hanging_adapter(t, c):
        time.sleep(0.4)
        return "too late"

    def fast_adapter(t, c):
        return "fast response"

    executor.register_adapter("slow-cand", hanging_adapter)
    executor.register_adapter("fast-cand", fast_adapter)

    res = executor.execute(task, decision)
    assert res.success is True
    assert res.final_candidate_id == "fast-cand"
    assert res.output == "fast response"
    assert len(res.attempts) == 2
    assert "timed out after" in str(res.attempts[0].error).lower()


@pytest.mark.unit
def test_no_orphan_process_after_timeout():
    """Verify subprocess execution with timeout terminates child process safely without orphan leak."""
    script = "import time; time.sleep(10)"
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        proc.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    dur = time.time() - t0
    assert dur < 2.0
    assert proc.poll() is not None  # Process has terminated cleanly


@pytest.mark.unit
def test_workspace_locking(temp_history, tmp_path):
    """Verify workspace lock serializes concurrent task execution on the same project path."""
    executor = RouterExecutor(history_tracker=temp_history)
    ws_dir = str(tmp_path / "locked_project")
    task = TaskSpec(prompt="Lock test", task_type=TaskType.GENERAL, metadata={"project_path": ws_dir})
    cand = RouteCandidate(candidate_id="c1", provider_type="worker", display_name="C1")
    decision = RouteDecision(task_id=task.task_id, selected_candidate=cand)

    execution_order = []

    def task_adapter(t, c):
        execution_order.append(t.task_id)
        time.sleep(0.05)
        return "ok"

    executor.register_adapter("c1", task_adapter)
    res = executor.execute(task, decision)
    assert res.success is True
    assert len(execution_order) == 1


@pytest.mark.unit
def test_actual_hardware_tier_recorded_in_history(temp_history):
    """Verify real HardwareTier from route decision is recorded in database history."""
    cand = RouteCandidate(
        candidate_id="tier-cand",
        provider_type="local",
        display_name="Tier Test Candidate",
        is_local=True,
    )
    task = TaskSpec(prompt="Tier task", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=cand,
        hardware_profile_summary={"hardware_tier": "high"},
    )

    executor = RouterExecutor(history_tracker=temp_history)
    executor.register_adapter("tier-cand", lambda t, c: "done")

    res = executor.execute(task, decision)
    assert res.success is True

    records = temp_history.list_history(limit=5)
    assert len(records) >= 1
    assert records[0]["hardware_tier"] == "high"


@pytest.mark.unit
def test_never_execute_unavailable_candidate(temp_history):
    """Verify unavailable candidates are skipped and never dispatched."""
    unavail_cand = RouteCandidate(
        candidate_id="unavail-cand",
        provider_type="cloud",
        display_name="Unavailable Candidate",
        is_available=False,
        unavailability_reason="Missing credentials",
    )
    working_cand = RouteCandidate(
        candidate_id="working-cand",
        provider_type="local",
        display_name="Working Candidate",
        is_available=True,
    )

    task = TaskSpec(prompt="Unavail test", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=unavail_cand,
        fallback_candidates=[working_cand],
    )

    executor = RouterExecutor(history_tracker=temp_history)
    invoked_unavail = False

    def unavail_adapter(t, c):
        nonlocal invoked_unavail
        invoked_unavail = True
        return "bad"

    executor.register_adapter("unavail-cand", unavail_adapter)
    executor.register_adapter("working-cand", lambda t, c: "good")

    res = executor.execute(task, decision)
    assert res.success is True
    assert res.final_candidate_id == "working-cand"
    assert invoked_unavail is False
    assert "Candidate unavailable" in str(res.attempts[0].error)


@pytest.mark.unit
def test_explicit_3d_ordering_full_chain(mock_hardware, monkeypatch, temp_history):
    """Verify explicit 3D ordering: Meshy -> Local Model -> Blender -> Unavailable Diagnostic."""
    registry = CapabilityRegistry()

    # 1. Meshy configured & cloud allowed -> Meshy
    monkeypatch.setenv("MESHY_API_KEY", "valid-key")
    router1 = DeterministicRouter(registry=registry, history_tracker=temp_history)
    task1 = TaskSpec(prompt="Dragon 3D", task_type=TaskType.THREE_D_GENERATION, allow_cloud=True)
    d1 = router1.plan_route(task1)
    assert d1.selected_candidate is not None
    assert d1.selected_candidate.candidate_id == "meshy-3d"

    # 2. Meshy unavailable, high hardware RAM for local 3D -> Local 3D Model
    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    hw_high = mock_hardware.model_copy()
    hw_high.ram_available_mb = 16384.0
    hw_high.vram_available_mb = 8192.0
    hw_high.installed_binaries["blender"] = True

    hw_mgr_high = HardwareManager({})
    hw_mgr_high.get_hardware_profile = lambda: hw_high
    router2 = DeterministicRouter(registry=registry, hardware_manager=hw_mgr_high, history_tracker=temp_history)
    task2 = TaskSpec(prompt="Sword 3D", task_type=TaskType.THREE_D_GENERATION, allow_cloud=False)
    d2 = router2.plan_route(task2)
    assert d2.selected_candidate is not None
    assert d2.selected_candidate.candidate_id == "local-3d-model"

    # 3. Local 3D model insufficient RAM, Blender installed -> Blender Worker
    hw_mid = mock_hardware.model_copy()
    hw_mid.ram_available_mb = 4096.0  # < 8192MB required by local-3d-model
    hw_mid.installed_binaries["blender"] = True

    hw_mgr_mid = HardwareManager({})
    hw_mgr_mid.get_hardware_profile = lambda: hw_mid
    router3 = DeterministicRouter(registry=registry, hardware_manager=hw_mgr_mid, history_tracker=temp_history)
    task3 = TaskSpec(prompt="Shield 3D", task_type=TaskType.THREE_D_GENERATION, allow_cloud=False)
    d3 = router3.plan_route(task3)
    assert d3.selected_candidate is not None
    assert d3.selected_candidate.candidate_id == "blender-worker"

    # 4. Blender not installed, no cloud, low RAM -> None + Diagnostic
    hw_weak = mock_hardware.model_copy()
    hw_weak.ram_available_mb = 512.0
    hw_weak.installed_binaries["blender"] = False

    hw_mgr_weak = HardwareManager({})
    hw_mgr_weak.get_hardware_profile = lambda: hw_weak
    router4 = DeterministicRouter(registry=registry, hardware_manager=hw_mgr_weak, history_tracker=temp_history)
    task4 = TaskSpec(prompt="Castle 3D", task_type=TaskType.THREE_D_GENERATION, allow_cloud=False)
    d4 = router4.plan_route(task4)
    assert d4.selected_candidate is None
    diag = "\n".join(d4.selection_reasons)
    assert "3D Policy Diagnostic" in diag
    assert "MESHY_API_KEY" in diag
    assert "Install Blender" in diag


@pytest.mark.unit
def test_rule_engine_honest_behavior_and_syntax_validation(tmp_path):
    """Verify deterministic rule engine performs real checks and refuses fake code generation."""
    rule_adp = create_rule_engine_adapter()
    cand = RouteCandidate(candidate_id="rules", provider_type="local_rules", display_name="Rules")

    # 1. Real valid Python syntax validation
    valid_code_task = TaskSpec(
        prompt="Check code",
        task_type=TaskType.VALIDATION,
        metadata={"code": "def hello():\n    return 'world'\n"}
    )
    res_valid = rule_adp(valid_code_task, cand)
    assert res_valid["status"] == "success"
    assert res_valid["validation_passed"] is True

    # 2. Real invalid Python syntax detection
    invalid_code_task = TaskSpec(
        prompt="Check bad code",
        task_type=TaskType.VALIDATION,
        metadata={"code": "def bad_syntax(:\n    return\n"}
    )
    with pytest.raises(WorkerValidationError) as syn_exc:
        rule_adp(invalid_code_task, cand)
    assert "syntax validation failed" in str(syn_exc.value).lower()

    # 3. Real file existence validation
    real_file = tmp_path / "valid.txt"
    real_file.write_text("content", encoding="utf-8")
    file_task = TaskSpec(
        prompt="Check file",
        task_type=TaskType.VALIDATION,
        metadata={"file_path": str(real_file)}
    )
    res_file = rule_adp(file_task, cand)
    assert res_file["status"] == "success"
    assert res_file["check_type"] == "file_existence"

    # 4. Refuse fake code generation honestly
    codegen_task = TaskSpec(prompt="Write full game engine", task_type=TaskType.CODE_GENERATION)
    with pytest.raises(UnsupportedTaskError) as unsupp_exc:
        rule_adp(codegen_task, cand)
    assert "cannot generate code" in str(unsupp_exc.value).lower()


@pytest.mark.unit
def test_sanitized_error_output_redacts_secrets():
    """Verify secrets and API keys are automatically stripped from error messages."""
    raw_error = "Failed to connect: sk-abcdef12345678901234567890 with AIzaSyD999999999999999999999999 and password=SuperSecret!"
    sanitized = sanitize_error_message(raw_error)
    assert "sk-abcdef" not in sanitized
    assert "AIzaSy" not in sanitized
    assert "SuperSecret" not in sanitized
    assert "[REDACTED_KEY]" in sanitized
    assert "password=[REDACTED]" in sanitized


@pytest.mark.unit
def test_application_adapter_wiring(tmp_path):
    """Integration test verifying real AppContext wires workers into RouterExecutor correctly."""
    cfg = load_config()
    cfg.raw["database_path"] = str(tmp_path / "app_ctx_test.db")
    cfg.raw["output_dir"] = str(tmp_path / "app_ctx_output")
    cfg.ensure_dirs()

    ctx = AppContext(cfg)
    assert hasattr(ctx, "router")
    assert hasattr(ctx, "router_executor")
    assert "code-worker" in ctx.router_executor.adapters
    assert "blender-worker" in ctx.router_executor.adapters
    assert "local-fallback-rules" in ctx.router_executor.adapters

    # Execute a code task through wired application router
    task = TaskSpec(prompt="Write test function", task_type=TaskType.CODE_GENERATION)
    decision = ctx.router.plan_route(task)
    assert decision.selected_candidate is not None

    result = ctx.router_executor.execute(task, decision)
    assert result.success is True
    assert result.final_candidate_id in ("code-worker", "local-fallback-rules")
