from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
from appsuite.core.dashboard import DashboardApp

def test_dashboard_routes():
    # Setup dummy context mock
    ctx = MagicMock()
    ctx.db.list_jobs.return_value = [{"id": "job_1", "status": "running"}]
    ctx.provider_manager.status.return_value = [{"id": "p_1", "name": "LLM Provider"}]
    
    dash = DashboardApp(ctx)
    assert dash.app is not None
    
    # Direct method retrieval tests to verify internal route bindings and safety fallbacks
    # Routes are registered with endpoints
    routes = {r.path: r.endpoint for r in dash.app.routes if hasattr(r, "path")}
    
    assert "/api/health" in routes
    assert "/api/jobs" in routes
    assert "/api/queue" in routes
    assert "/api/providers" in routes
    assert "/api/projects" in routes
    assert "/api/benchmarks" in routes
    assert "/api/workers" in routes
    
    # Test route return values directly
    assert routes["/api/health"]()["status"] == "healthy"
    assert len(routes["/api/jobs"]()) == 1
    assert routes["/api/jobs"]()[0]["id"] == "job_1"
