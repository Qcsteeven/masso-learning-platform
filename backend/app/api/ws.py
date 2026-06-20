"""WebSocket handlers — Phase 5.3 (terminal) + Phase 5.4 (events / status / monitoring).

Auth strategy
-------------
- terminal, events, status  : one-time short-lived token (TTL 60 s) passed as
                              ``?token=`` query param (avoids sending Bearer in
                              the WS upgrade request where browsers do not support
                              the Authorization header).
- admin monitoring          : JWT Bearer via the ``token`` query param, decoded
                              through the same ``decode_access_token`` function
                              used by REST routes.  Role admin or sysadmin is
                              required.

Redis is injected via ``Depends(get_redis)`` on every handler so that unit
tests can override it cleanly through FastAPI's dependency override mechanism.
"""
from __future__ import annotations

import contextlib
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.db.redis import get_redis
from app.services.terminal_service import TerminalService, get_terminal_service

_log = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# ── helpers ───────────────────────────────────────────────────────────────────

async def _verify_session_token(
    redis: object,
    token: str,
    session_id: str,
) -> bool:
    """Return True and consume the one-time token if it matches *session_id*."""
    stored = await redis.get(f"terminal_token:{token}")  # type: ignore[union-attr]
    if stored != session_id:
        return False
    await redis.delete(f"terminal_token:{token}")  # type: ignore[union-attr]
    return True


async def _pubsub_forward(ws: WebSocket, channel: str, redis: object) -> None:
    """Subscribe to *channel*, forward every message to *ws*, unsubscribe on disconnect.

    *redis* is passed in explicitly so it can be injected in tests.
    """
    pubsub = redis.pubsub()  # type: ignore[union-attr]
    await pubsub.subscribe(channel)
    _log.debug("WS subscribed to Redis channel %s", channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            if ws.client_state != WebSocketState.CONNECTED:
                break
            data = message["data"]
            # decode_responses=True → data is already str; guard for bytes anyway
            if isinstance(data, bytes):
                data = data.decode()
            await ws.send_text(data)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        _log.warning("pubsub_forward error on channel %s: %s", channel, exc)
    finally:
        with contextlib.suppress(Exception):  # noqa: BLE001
            await pubsub.unsubscribe(channel)
        with contextlib.suppress(Exception):  # noqa: BLE001
            await pubsub.aclose()


# ── Phase 5.3 — Terminal ──────────────────────────────────────────────────────

@router.websocket("/ws/sessions/{session_id}/terminal")
async def ws_terminal(
    session_id: str,
    ws: WebSocket,
    token: str = Query(..., description="One-time terminal token (TTL 60 s)"),
    terminal_svc: TerminalService = Depends(get_terminal_service),  # noqa: B008
    redis: Annotated[object, Depends(get_redis)] = None,  # type: ignore[assignment]
) -> None:
    """Bidirectional WebSocket ↔ Docker exec bridge for the sandbox shell.

    The caller must first obtain a short-lived token from
    ``POST /sessions/{id}/terminal-token`` and pass it as ``?token=``.
    The token is consumed on first use.
    """
    if not await _verify_session_token(redis, token, session_id):
        _log.warning("ws_terminal: invalid token for session %s", session_id)
        await ws.close(1008)  # Policy Violation
        return

    await ws.accept()
    await terminal_svc.attach_to_container(session_id, ws)


# ── Phase 5.4 — Session events ────────────────────────────────────────────────

@router.websocket("/ws/sessions/{session_id}/events")
async def ws_events(
    session_id: str,
    ws: WebSocket,
    token: str = Query(..., description="One-time session token (TTL 60 s)"),
    redis: Annotated[object, Depends(get_redis)] = None,  # type: ignore[assignment]
) -> None:
    """Push stream of session events (incidents, hints, warnings, security, check_status).

    Messages arrive as raw JSON strings matching the ``SessionEventMessage``
    discriminated union defined in ``app/schemas/websocket.py``.
    """
    if not await _verify_session_token(redis, token, session_id):
        _log.warning("ws_events: invalid token for session %s", session_id)
        await ws.close(1008)
        return

    await ws.accept()
    await _pubsub_forward(ws, f"session:{session_id}:events", redis)


# ── Phase 5.4 — Session status ────────────────────────────────────────────────

@router.websocket("/ws/sessions/{session_id}/status")
async def ws_status(
    session_id: str,
    ws: WebSocket,
    token: str = Query(..., description="One-time session token (TTL 60 s)"),
    redis: Annotated[object, Depends(get_redis)] = None,  # type: ignore[assignment]
) -> None:
    """Push stream of status-change events for a session.

    Messages are ``StatusChangeEvent`` JSON objects:
    ``{"type": "status_change", "status": "...", "timestamp": "..."}``.
    """
    if not await _verify_session_token(redis, token, session_id):
        _log.warning("ws_status: invalid token for session %s", session_id)
        await ws.close(1008)
        return

    await ws.accept()
    await _pubsub_forward(ws, f"session:{session_id}:status", redis)


# ── Phase 5.4 — Admin monitoring ─────────────────────────────────────────────

@router.websocket("/ws/admin/monitoring")
async def ws_monitoring(
    ws: WebSocket,
    token: str = Query(..., description="JWT access token for admin/sysadmin"),
    redis: Annotated[object, Depends(get_redis)] = None,  # type: ignore[assignment]
) -> None:
    """Push stream of platform monitoring events (queue depth, LLM provider, sandbox, alerts).

    Requires ``admin`` or ``sysadmin`` role.  The JWT access token must be
    passed as ``?token=`` because browsers cannot set the ``Authorization``
    header on WebSocket upgrade requests.

    Messages match the ``MonitoringMessage`` discriminated union.
    """
    from app.core.errors import AUTH_FORBIDDEN  # noqa: PLC0415
    from app.core.security import decode_access_token  # noqa: PLC0415
    from app.db.postgres import get_db  # noqa: PLC0415
    from app.services.user_service import get_user_roles  # noqa: PLC0415

    # Decode JWT — raises 401 HTTPException on bad/expired token;
    # convert to WS close so the upgrade is rejected cleanly.
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001
        await ws.close(1008)
        return

    user_id: str | None = payload.get("sub")  # type: ignore[assignment]
    if user_id is None:
        await ws.close(1008)
        return

    # RBAC check — admin or sysadmin only
    try:
        async for db in get_db():
            user_roles = await get_user_roles(db, __import__("uuid").UUID(user_id))
            break
    except Exception:  # noqa: BLE001
        await ws.close(1011)
        return

    if not any(r in user_roles for r in ("admin", "sysadmin")):
        _log.warning("ws_monitoring: forbidden for user %s (roles %s)", user_id, user_roles)
        await ws.send_text(json.dumps({"type": "error", "code": AUTH_FORBIDDEN}))
        await ws.close(1008)
        return

    await ws.accept()
    await _pubsub_forward(ws, "masso:monitoring", redis)
