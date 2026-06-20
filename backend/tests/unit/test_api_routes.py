"""Unit tests for API route registration — no database required."""
from fastapi.testclient import TestClient

from app.main import create_app

# Required route prefixes from ТП §9 Таблица 8 + WebSocket channels
REQUIRED_PREFIXES = [
    "/auth/",
    "/users/",
    "/skills/",
    "/scenarios/",
    "/sessions/",
    "/events/",
    "/verification/",
    "/reports/",
    "/admin/llm/",
    "/admin/sandbox/",
]

REQUIRED_WEBSOCKET_PATHS = [
    "/ws/sessions/{session_id}/terminal",
    "/ws/sessions/{session_id}/events",
    "/ws/sessions/{session_id}/status",
    "/ws/admin/monitoring",
]


def _app() -> object:
    """Create app without triggering lifespan (DB startup)."""
    return create_app()


def test_health_endpoint_returns_200() -> None:
    app = _app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    # Health endpoint skips DB — should be 200
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"


def _route_paths(app: object) -> list[str]:
    """Recursively collect all registered paths including from included routers."""
    paths: list[str] = []
    for r in app.routes:  # type: ignore[attr-defined]
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "original_router"):
            # FastAPI 0.136+ wraps include_router() in _IncludedRouter
            for sub in r.original_router.routes:
                if hasattr(sub, "path"):
                    paths.append(sub.path)
    return paths


def test_all_required_route_prefixes_registered() -> None:
    app = _app()
    routes = _route_paths(app)

    for prefix in REQUIRED_PREFIXES:
        has_prefix = any(r.startswith(prefix) or r == prefix.rstrip("/") for r in routes)
        assert has_prefix, f"Missing route prefix: {prefix}\nRegistered: {sorted(routes)}"


def test_no_route_returns_404() -> None:
    """Every defined GET path must return something other than 404."""
    app = _app()
    client = TestClient(app, raise_server_exceptions=False)

    must_not_404 = [
        "/health",
        "/users/",
        "/skills/graph",
        "/skills/recommendations",
        "/reports/",
        "/admin/llm/providers",
        "/admin/sandbox/profiles",
        "/admin/sandbox/health",
    ]
    for path in must_not_404:
        resp = client.get(path)
        assert resp.status_code != 404, f"Route {path} returned 404 (not registered)"


def test_stub_routes_return_error_envelope() -> None:
    """Stub (501) routes that are not auth-protected return a valid error envelope."""
    app = _app()
    client = TestClient(app, raise_server_exceptions=False)

    # /users/ is now auth-protected (returns 401/403), so we test a non-auth route
    # that still returns our envelope format.
    resp = client.get("/skills/graph")
    body = resp.json()
    assert "status" in body
    assert "request_id" in body


def test_openapi_json_contains_all_prefixes() -> None:
    from fastapi import FastAPI as _FastAPI

    from app.api import (  # noqa: PLC0415
        admin_llm,
        admin_sandbox,
        auth,
        events,
        health,
        reports,
        scenarios,
        sessions,
        skills,
        users,
        verification,
        ws,
    )

    # Build minimal app with openapi enabled
    app = _FastAPI(title="МАССО API", version="test")
    for mod in [health, auth, users, skills, scenarios, sessions, events,
                verification, reports, admin_llm, admin_sandbox, ws]:
        app.include_router(mod.router)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths: set[str] = set(resp.json().get("paths", {}).keys())

    for prefix in REQUIRED_PREFIXES:
        has_prefix = any(p.startswith(prefix) or p == prefix.rstrip("/") for p in paths)
        assert has_prefix, f"OpenAPI missing prefix {prefix}. Available: {sorted(paths)}"


def test_websocket_paths_registered() -> None:
    app = _app()
    ws_paths = set(_route_paths(app))
    for ws_path in REQUIRED_WEBSOCKET_PATHS:
        assert ws_path in ws_paths, f"WebSocket path not registered: {ws_path}"
