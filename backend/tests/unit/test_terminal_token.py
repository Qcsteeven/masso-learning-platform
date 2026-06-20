"""Unit tests for Phase 5.3 — terminal token endpoint and WebSocket auth guard.

Uses FastAPI TestClient with dependency overrides.  No real Redis or PostgreSQL.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import sessions, ws
from app.models.user import User

# ── Helpers / fixtures ────────────────────────────────────────────────────────

def _make_user() -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.status = "active"
    return u


def _build_app(user: User, redis_mock: AsyncMock) -> FastAPI:
    """Build a minimal FastAPI app with dependency overrides."""
    from app.core.deps import get_current_user  # noqa: PLC0415
    from app.db.redis import get_redis  # noqa: PLC0415

    app = FastAPI()
    app.include_router(sessions.router)
    app.include_router(ws.router)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_redis] = lambda: redis_mock

    return app


def _make_redis_for_token(session_id: str, token: str) -> AsyncMock:
    """Return a Redis mock that emulates a stored terminal token."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=session_id)
    redis.delete = AsyncMock(return_value=1)
    return redis


# ── POST /sessions/{id}/terminal-token ───────────────────────────────────────

def test_terminal_token_returns_token_and_expiry() -> None:
    """POST /sessions/{id}/terminal-token must return a token string and expires_in=60."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)

    app = _build_app(user, redis_mock)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post(f"/sessions/{session_id}/terminal-token")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "token" in data
    assert isinstance(data["token"], str)
    assert len(data["token"]) > 0
    assert data["expires_in"] == 60


def test_terminal_token_stored_in_redis_with_ttl() -> None:
    """POST /sessions/{id}/terminal-token must call redis.set with ex=60."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)

    app = _build_app(user, redis_mock)
    client = TestClient(app, raise_server_exceptions=True)

    client.post(f"/sessions/{session_id}/terminal-token")

    redis_mock.set.assert_awaited_once()
    call_kwargs = redis_mock.set.call_args
    # Key pattern: terminal_token:{token}
    key: str = call_kwargs.args[0]
    value: str = call_kwargs.args[1]
    assert key.startswith("terminal_token:")
    assert value == session_id
    assert call_kwargs.kwargs.get("ex") == 60


def test_terminal_token_requires_auth() -> None:
    """Without auth override, the endpoint must return 401/403."""
    from fastapi import FastAPI as _FastAPI  # noqa: PLC0415

    app = _FastAPI()
    app.include_router(sessions.router)

    client = TestClient(app, raise_server_exceptions=False)
    session_id = str(uuid.uuid4())
    resp = client.post(f"/sessions/{session_id}/terminal-token")
    # No auth provided → 401 Unauthorized (OAuth2 scheme)
    assert resp.status_code == 401


def test_terminal_token_different_for_each_call() -> None:
    """Each call must produce a distinct token (secrets.token_urlsafe is random)."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)

    app = _build_app(user, redis_mock)
    client = TestClient(app, raise_server_exceptions=True)

    tokens = set()
    for _ in range(5):
        resp = client.post(f"/sessions/{session_id}/terminal-token")
        tokens.add(resp.json()["data"]["token"])

    assert len(tokens) == 5, "Each terminal token must be unique"


# ── WebSocket /ws/sessions/{id}/terminal — bad token ─────────────────────────
#
# Starlette TestClient raises WebSocketDisconnect from within
# websocket_connect().__enter__() when the server sends close() before accept().
# We must catch it at the outer "with" level via pytest.raises().

def test_ws_terminal_invalid_token_closes_1008() -> None:
    """WebSocket upgrade with a wrong token must be closed with code 1008."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    # Redis returns None (token not found) for any key
    redis_miss = AsyncMock()
    redis_miss.get = AsyncMock(return_value=None)
    redis_miss.delete = AsyncMock(return_value=0)

    app = _build_app(user, redis_miss)
    client = TestClient(app, raise_server_exceptions=False)

    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
        f"/ws/sessions/{session_id}/terminal?token=bad-token"
    ):
        pass  # never reached — server closes before accept

    assert exc_info.value.code == 1008


def test_ws_terminal_wrong_session_in_token_closes_1008() -> None:
    """Token stored for a different session_id must cause close(1008)."""
    session_id = str(uuid.uuid4())
    other_session_id = str(uuid.uuid4())
    user = _make_user()

    # Redis returns the *other* session_id — mismatch
    redis_mismatch = AsyncMock()
    redis_mismatch.get = AsyncMock(return_value=other_session_id)
    redis_mismatch.delete = AsyncMock(return_value=1)

    app = _build_app(user, redis_mismatch)
    client = TestClient(app, raise_server_exceptions=False)

    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
        f"/ws/sessions/{session_id}/terminal?token=some-token"
    ):
        pass

    assert exc_info.value.code == 1008


# ── WebSocket /ws/sessions/{id}/events — bad token ───────────────────────────

def test_ws_events_invalid_token_closes_1008() -> None:
    """WebSocket events channel with invalid token must close without delivering messages."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    redis_miss = AsyncMock()
    redis_miss.get = AsyncMock(return_value=None)
    redis_miss.delete = AsyncMock(return_value=0)

    app = _build_app(user, redis_miss)
    client = TestClient(app, raise_server_exceptions=False)

    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
        f"/ws/sessions/{session_id}/events?token=invalid"
    ):
        pass

    assert exc_info.value.code == 1008


# ── WebSocket /ws/sessions/{id}/status — bad token ───────────────────────────

def test_ws_status_invalid_token_closes_1008() -> None:
    """WebSocket status channel with invalid token must close cleanly."""
    session_id = str(uuid.uuid4())
    user = _make_user()

    redis_miss = AsyncMock()
    redis_miss.get = AsyncMock(return_value=None)
    redis_miss.delete = AsyncMock(return_value=0)

    app = _build_app(user, redis_miss)
    client = TestClient(app, raise_server_exceptions=False)

    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
        f"/ws/sessions/{session_id}/status?token=invalid"
    ):
        pass

    assert exc_info.value.code == 1008
