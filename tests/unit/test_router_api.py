"""Unit tests for PyFlare router API endpoints and authentication requirements."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pyflare.core.config import load_config
from pyflare.core.main import create_app


@pytest.fixture
def api_client(tmp_path) -> TestClient:
    """Provide a TestClient with a fresh app context."""
    cfg = load_config()
    cfg.raw["database_path"] = str(tmp_path / "test_router_api.db")
    cfg.raw["output_dir"] = str(tmp_path / "output")
    cfg.ensure_dirs()
    app = create_app(cfg)
    return TestClient(app)


@pytest.mark.unit
def test_router_capabilities_endpoint(api_client):
    """GET /router/capabilities returns candidate list without requiring auth."""
    resp = api_client.get("/router/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    cand_ids = [c["candidate_id"] for c in data]
    assert "openai-cloud" in cand_ids
    assert "blender-worker" in cand_ids


@pytest.mark.unit
def test_router_hardware_endpoint(api_client):
    """GET /router/hardware returns telemetry without requiring auth."""
    resp = api_client.get("/router/hardware")
    assert resp.status_code == 200
    data = resp.json()
    assert "hardware_tier" in data
    assert "cpu_cores_logical" in data
    assert "ram_total_mb" in data


@pytest.mark.unit
def test_router_plan_endpoint(api_client):
    """POST /router/plan returns routing decision without requiring auth."""
    task_payload = {
        "prompt": "Create a python CLI calculator",
        "task_type": "code_generation",
        "allow_cloud": True,
        "privacy_level": "public",
    }
    resp = api_client.post("/router/plan", json=task_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "selected_candidate" in data
    assert "score" in data
    assert "selection_reasons" in data


@pytest.mark.unit
def test_router_execute_requires_auth(api_client, monkeypatch):
    """POST /router/execute enforces authentication by default."""
    monkeypatch.setenv("PYFLARE_REQUIRE_AUTH", "true")
    monkeypatch.setenv("PYFLARE_API_KEY", "test-secret-key-999")

    task_payload = {
        "prompt": "Run benchmark calculation",
        "task_type": "general",
        "privacy_level": "public",
    }

    # Request without key -> 401
    resp_unauth = api_client.post("/router/execute", json=task_payload)
    assert resp_unauth.status_code == 401

    # Request with valid key -> 200
    resp_auth = api_client.post(
        "/router/execute",
        json=task_payload,
        headers={"X-API-Key": "test-secret-key-999"}
    )
    assert resp_auth.status_code == 200
    data = resp_auth.json()
    assert data["success"] is True
    assert data["final_candidate_id"] is not None


@pytest.mark.unit
def test_router_history_requires_auth(api_client, monkeypatch):
    """GET /router/history enforces authentication by default."""
    monkeypatch.setenv("PYFLARE_REQUIRE_AUTH", "true")
    monkeypatch.setenv("PYFLARE_API_KEY", "test-secret-key-999")

    # Request without key -> 401
    resp_unauth = api_client.get("/router/history")
    assert resp_unauth.status_code == 401

    # Request with valid key -> 200
    resp_auth = api_client.get(
        "/router/history",
        headers={"Authorization": "Bearer test-secret-key-999"}
    )
    assert resp_auth.status_code == 200
    assert isinstance(resp_auth.json(), list)
