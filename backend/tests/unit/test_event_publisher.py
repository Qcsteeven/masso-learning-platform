"""Unit tests for app.services.event_publisher (Phase 5.4).

Redis is mocked — no real broker required.
asyncio_mode = "auto" in pyproject.toml — no @pytest.mark.asyncio decorators needed.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_redis_mock() -> AsyncMock:
    """Return an AsyncMock that satisfies redis.publish() calls."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


# ── publish_session_event ─────────────────────────────────────────────────────

async def test_publish_session_event_correct_channel() -> None:
    """publish_session_event must publish to session:{id}:events."""
    session_id = "abc-123"
    event = {
        "type": "incident",
        "severity": "high",
        "message": "CPU spike",
        "timestamp": "2026-06-20T00:00:00+00:00",
    }
    redis_mock = _make_redis_mock()

    with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
        from app.services.event_publisher import publish_session_event
        await publish_session_event(session_id, event)

    redis_mock.publish.assert_awaited_once()
    channel, payload = redis_mock.publish.call_args.args
    assert channel == f"session:{session_id}:events"
    decoded = json.loads(payload)
    assert decoded["type"] == "incident"
    assert decoded["severity"] == "high"


async def test_publish_session_event_payload_is_valid_json() -> None:
    """The payload forwarded to Redis must be valid JSON."""
    redis_mock = _make_redis_mock()
    event: dict[str, object] = {
        "type": "hint",
        "number": 1,
        "text": "check the config",
        "penalty_percent": 10.0,
    }

    with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
        from app.services.event_publisher import publish_session_event
        await publish_session_event("sess-1", event)

    _, payload = redis_mock.publish.call_args.args
    decoded = json.loads(payload)
    assert decoded["penalty_percent"] == 10.0


# ── publish_status_change ─────────────────────────────────────────────────────

async def test_publish_status_change_correct_channel() -> None:
    """publish_status_change must publish to session:{id}:status."""
    session_id = "sess-xyz"
    redis_mock = _make_redis_mock()

    with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
        from app.services.event_publisher import publish_status_change
        await publish_status_change(session_id, "active")

    channel, _ = redis_mock.publish.call_args.args
    assert channel == f"session:{session_id}:status"


async def test_publish_status_change_payload_shape() -> None:
    """Payload must contain type='status_change', the correct status and a timestamp."""
    redis_mock = _make_redis_mock()

    with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
        from app.services.event_publisher import publish_status_change
        await publish_status_change("sess-1", "completed")

    _, payload = redis_mock.publish.call_args.args
    decoded = json.loads(payload)
    assert decoded["type"] == "status_change"
    assert decoded["status"] == "completed"
    assert "timestamp" in decoded
    # timestamp must be a non-empty ISO string
    assert isinstance(decoded["timestamp"], str)
    assert len(decoded["timestamp"]) > 0


async def test_publish_status_change_different_statuses() -> None:
    """publish_status_change must work for every valid status value."""
    valid_statuses = [
        "created", "starting", "active", "paused",
        "submitted", "checking", "completed", "failed",
    ]
    for new_status in valid_statuses:
        redis_mock = _make_redis_mock()
        with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
            from app.services.event_publisher import publish_status_change
            await publish_status_change("s", new_status)
        _, payload = redis_mock.publish.call_args.args
        assert json.loads(payload)["status"] == new_status


# ── publish_monitoring_event ──────────────────────────────────────────────────

async def test_publish_monitoring_event_correct_channel() -> None:
    """publish_monitoring_event must publish to masso:monitoring."""
    redis_mock = _make_redis_mock()
    event: dict[str, object] = {"type": "queue", "name": "scenario_generation", "depth": 5}

    with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
        from app.services.event_publisher import publish_monitoring_event
        await publish_monitoring_event(event)

    channel, payload = redis_mock.publish.call_args.args
    assert channel == "masso:monitoring"
    decoded = json.loads(payload)
    assert decoded["type"] == "queue"
    assert decoded["depth"] == 5


async def test_publish_monitoring_event_various_types() -> None:
    """publish_monitoring_event must handle all MonitoringMessage subtypes."""
    events: list[dict[str, object]] = [
        {"type": "provider", "code": "openai", "mode": "external", "status": "healthy"},
        {"type": "sandbox", "session_id": "abc", "action": "created"},
        {"type": "alert", "severity": "critical", "message": "disk full"},
    ]
    for event in events:
        redis_mock = _make_redis_mock()
        with patch("app.services.event_publisher.get_redis", return_value=redis_mock):
            from app.services.event_publisher import publish_monitoring_event
            await publish_monitoring_event(event)
        channel, payload = redis_mock.publish.call_args.args
        assert channel == "masso:monitoring"
        assert json.loads(payload)["type"] == event["type"]
