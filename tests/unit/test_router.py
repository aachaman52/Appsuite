"""Unit tests for PyFlare's Deterministic Routing Layer."""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from pyflare.core.hardware_manager import HardwareManager
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

    # Task requires non-existent capability
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
    weak_hw.ram_available_mb = 512.0  # Very low RAM available

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
def test_executor_fallback_on_provider_failure(temp_history):
    """Verify executor tries primary route, catches transient failure, and succeeds on fallback."""
    primary = RouteCandidate(
        candidate_id="failing-primary",
        provider_type="cloud",
        display_name="Failing Primary",
        is_local=False,
        supported_task_types=[TaskType.GENERAL],
    )
    fallback = RouteCandidate(
        candidate_id="working-fallback",
        provider_type="local",
        display_name="Working Fallback",
        is_local=True,
        supported_task_types=[TaskType.GENERAL],
    )

    task = TaskSpec(prompt="Execute test", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=primary,
        fallback_candidates=[fallback],
    )

    executor = RouterExecutor(history_tracker=temp_history, max_retries_per_candidate=1)

    def failing_adapter(t, c):
        raise ConnectionResetError("Remote server closed connection")

    def working_adapter(t, c):
        return {"result": "recovered_via_fallback"}

    executor.register_adapter("failing-primary", failing_adapter)
    executor.register_adapter("working-fallback", working_adapter)

    res = executor.execute(task, decision)
    assert res.success is True
    assert res.final_candidate_id == "working-fallback"
    assert res.output == {"result": "recovered_via_fallback"}
    assert len(res.attempts) == 3


@pytest.mark.unit
def test_executor_non_retryable_auth_error_no_retry(temp_history):
    """Verify non-retryable 401 authentication errors do NOT waste retries on same candidate."""
    primary = RouteCandidate(
        candidate_id="unauth-primary",
        provider_type="cloud",
        display_name="Unauthenticated Primary",
        is_local=False,
    )
    fallback = RouteCandidate(
        candidate_id="local-fallback",
        provider_type="local",
        display_name="Local Fallback",
        is_local=True,
    )

    task = TaskSpec(prompt="Auth test", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=primary,
        fallback_candidates=[fallback],
    )

    executor = RouterExecutor(history_tracker=temp_history, max_retries_per_candidate=2)

    def auth_fail_adapter(t, c):
        raise PermissionError("401 Unauthorized: Invalid API key")

    def local_adapter(t, c):
        return "ok"

    executor.register_adapter("unauth-primary", auth_fail_adapter)
    executor.register_adapter("local-fallback", local_adapter)

    res = executor.execute(task, decision)
    assert res.success is True
    assert len(res.attempts) == 2
    assert res.attempts[0].is_retryable is False


@pytest.mark.unit
def test_fallback_loop_prevention(temp_history):
    """Verify executor never re-executes an already attempted candidate."""
    cand = RouteCandidate(
        candidate_id="flaky-candidate",
        provider_type="mock",
        display_name="Flaky Candidate",
        is_local=True,
    )

    task = TaskSpec(prompt="Loop test", task_type=TaskType.GENERAL)
    decision = RouteDecision(
        task_id=task.task_id,
        selected_candidate=cand,
        fallback_candidates=[cand, cand],
    )

    executor = RouterExecutor(history_tracker=temp_history, max_retries_per_candidate=0)

    def fail_adapter(t, c):
        raise RuntimeError("Always fails")

    executor.register_adapter("flaky-candidate", fail_adapter)

    res = executor.execute(task, decision)
    assert res.success is False
    assert len(res.attempts) == 1


@pytest.mark.unit
def test_historical_performance_bayesian_smoothing(temp_history):
    """Verify Bayesian smoothing prevents low sample counts from breaking scoring."""
    stats0 = temp_history.get_candidate_stats("cand-1")
    assert stats0["has_sufficient_samples"] is False
    assert stats0["smoothed_success_rate"] == 0.85

    temp_history.record_outcome(RouteOutcome(
        task_id="t1",
        candidate_id="cand-1",
        task_type=TaskType.GENERAL,
        success=False,
        duration_seconds=1.0,
        cost_usd=0.0,
    ))

    stats1 = temp_history.get_candidate_stats("cand-1")
    assert stats1["sample_count"] == 1
    assert stats1["raw_success_rate"] == 0.0
    assert stats1["smoothed_success_rate"] > 0.65
    assert stats1["has_sufficient_samples"] is False


@pytest.mark.unit
def test_3d_routing_policy(mock_hardware, monkeypatch, temp_history):
    """Verify 3D routing policy precedence (Cloud 3D -> Local Model -> Blender -> Clear Diagnostic)."""
    registry = CapabilityRegistry()

    # Case A: When Meshy API key is configured, Meshy is chosen for 3D generation
    monkeypatch.setenv("MESHY_API_KEY", "mock-meshy-key")
    router = DeterministicRouter(registry=registry, history_tracker=temp_history)
    task = TaskSpec(prompt="Create 3D dragon mesh", task_type=TaskType.THREE_D_GENERATION, allow_cloud=True)

    dec_cloud = router.plan_route(task)
    assert dec_cloud.selected_candidate is not None
    assert dec_cloud.selected_candidate.candidate_id == "meshy-3d"

    # Case B: When Meshy is unavailable and Cloud is disallowed, but Blender is installed -> route to Blender
    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    hw_blender = mock_hardware.model_copy()
    hw_blender.installed_binaries["blender"] = True
    hw_blender.ram_available_mb = 4096.0

    hw_mgr = HardwareManager({})
    hw_mgr.get_hardware_profile = lambda: hw_blender

    router_blender = DeterministicRouter(registry=registry, hardware_manager=hw_mgr, history_tracker=temp_history)
    task_local = TaskSpec(prompt="Create 3D sword", task_type=TaskType.THREE_D_GENERATION, allow_cloud=False)

    dec_blender = router_blender.plan_route(task_local)
    assert dec_blender.selected_candidate is not None
    assert dec_blender.selected_candidate.candidate_id == "blender-worker"


@pytest.mark.unit
def test_no_available_3d_route_diagnostic_message(mock_hardware, monkeypatch, temp_history):
    """Verify when no 3D route is possible, router returns a clear actionable diagnostic."""
    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    weak_hw = mock_hardware.model_copy()
    weak_hw.installed_binaries["blender"] = False
    weak_hw.ram_available_mb = 512.0  # Cannot run local 3D model

    hw_mgr = HardwareManager({})
    hw_mgr.get_hardware_profile = lambda: weak_hw

    router = DeterministicRouter(hardware_manager=hw_mgr, history_tracker=temp_history)
    task = TaskSpec(prompt="Synthesize 3D spaceship", task_type=TaskType.THREE_D_GENERATION, allow_cloud=False)

    dec = router.plan_route(task)
    assert dec.selected_candidate is None
    diag_reasons = "\n".join(dec.selection_reasons)
    assert "3D Policy Diagnostic" in diag_reasons
    assert "MESHY_API_KEY" in diag_reasons
    assert "Install Blender" in diag_reasons
