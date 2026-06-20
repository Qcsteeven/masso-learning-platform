"""Event publisher — Redis Pub/Sub helpers for WebSocket fan-out (Phase 5.4).

Imported via lazy import from session_service to avoid circular imports:

    from app.services import event_publisher  # noqa: PLC0415
    await event_publisher.publish_status_change(str(session_id), "active")

``get_redis`` is imported at module level (not lazily) so that unit tests can
patch ``app.services.event_publisher.get_redis`` without a ``create=True`` hack.
``app.db.redis`` never imports anything from ``app.services``, so there is no
circular dependency here.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.db.redis import get_redis

_log = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


async def publish_session_event(session_id: str, event: dict[str, object]) -> None:
    """Publish an arbitrary session event to Redis Pub/Sub channel ``session:{id}:events``.

    Subscribers are the ``/ws/sessions/{id}/events`` WebSocket handlers.
    """
    redis = get_redis()
    channel = f"session:{session_id}:events"
    payload = json.dumps(event)
    await redis.publish(channel, payload)
    _log.debug("Published session event to %s: %s", channel, payload[:120])


async def publish_status_change(session_id: str, new_status: str) -> None:
    """Publish a status-change event to Redis Pub/Sub channel ``session:{id}:status``.

    Subscribers are the ``/ws/sessions/{id}/status`` WebSocket handlers.
    """
    redis = get_redis()
    channel = f"session:{session_id}:status"
    payload = json.dumps(
        {"type": "status_change", "status": new_status, "timestamp": _utcnow_iso()}
    )
    await redis.publish(channel, payload)
    _log.debug("Published status change to %s: %s", channel, new_status)


async def publish_monitoring_event(event: dict[str, object]) -> None:
    """Publish a monitoring event to Redis Pub/Sub channel ``masso:monitoring``.

    Subscribers are the ``/ws/admin/monitoring`` WebSocket handlers.
    """
    redis = get_redis()
    channel = "masso:monitoring"
    payload = json.dumps(event)
    await redis.publish(channel, payload)
    _log.debug("Published monitoring event to %s: %s", channel, payload[:120])
