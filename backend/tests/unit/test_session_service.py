"""Unit tests for session_service.transition_status (Phase 4.4).

Uses in-memory AsyncMock DB sessions — no real PostgreSQL.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session_obj(
    session_id: uuid.UUID,
    current_status: str,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock LearningSession ORM object."""
    obj = MagicMock()
    obj.id = session_id
    obj.status = current_status
    obj.user_id = user_id or uuid.uuid4()
    obj.started_at = None
    obj.finished_at = None
    obj.run_id = uuid.uuid4()
    obj.trace_id = uuid.uuid4()
    return obj


def _make_db(session_obj: MagicMock) -> AsyncMock:
    """Return a mock AsyncSession that returns *session_obj* from scalar_one_or_none."""
    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=session_obj)
    db.execute = AsyncMock(return_value=scalar_result)
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ── Valid transitions ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "from_status,to_status",
    [
        ("created", "starting"),
        ("starting", "active"),
        ("active", "paused"),
        ("paused", "active"),
        ("active", "submitted"),
        ("submitted", "checking"),
        ("checking", "completed"),
        ("checking", "failed"),
    ],
)
async def test_valid_transitions(from_status: str, to_status: str) -> None:
    """All allowed transitions from ТП §8 must succeed and return updated status."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, from_status)
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    result = await transition_status(db, session_id, to_status)
    assert result.status == to_status


# ── Invalid transition: active → completed ────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_transition_active_to_completed() -> None:
    """active → completed is NOT allowed; must raise HTTPException(409)."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, "active")
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    with pytest.raises(HTTPException) as exc_info:
        await transition_status(db, session_id, "completed")

    assert exc_info.value.status_code == 409


# ── Invalid transition: created → completed ────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_transition_created_to_completed() -> None:
    """created → completed is NOT allowed; must raise HTTPException(409)."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, "created")
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    with pytest.raises(HTTPException) as exc_info:
        await transition_status(db, session_id, "completed")

    assert exc_info.value.status_code == 409


# ── Invalid transition: submitted → failed (must go through checking first) ───

@pytest.mark.asyncio
async def test_invalid_transition_submitted_to_failed() -> None:
    """submitted → failed is NOT allowed (must go submitted→checking→failed)."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, "submitted")
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    with pytest.raises(HTTPException) as exc_info:
        await transition_status(db, session_id, "failed")

    assert exc_info.value.status_code == 409


# ── Session not found → 404 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transition_session_not_found() -> None:
    """transition_status must raise HTTPException(404) when session does not exist."""
    session_id = uuid.uuid4()
    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute = AsyncMock(return_value=scalar_result)

    from app.services.session_service import transition_status

    with pytest.raises(HTTPException) as exc_info:
        await transition_status(db, session_id, "starting")

    assert exc_info.value.status_code == 404


# ── started_at set on first active transition ─────────────────────────────────

@pytest.mark.asyncio
async def test_started_at_set_on_first_active() -> None:
    """Transitioning to 'active' for the first time must set started_at."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, "starting")
    session_obj.started_at = None
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    result = await transition_status(db, session_id, "active")
    assert result.started_at is not None


# ── finished_at set on completed/failed ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["completed", "failed"])
async def test_finished_at_set_on_terminal(terminal_status: str) -> None:
    """Transitioning to a terminal state must set finished_at."""
    session_id = uuid.uuid4()
    session_obj = _make_session_obj(session_id, "checking")
    session_obj.finished_at = None
    db = _make_db(session_obj)

    from app.services.session_service import transition_status

    result = await transition_status(db, session_id, terminal_status)
    assert result.finished_at is not None
