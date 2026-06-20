"""Session service — business logic for learning session lifecycle."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import HINT_LIMIT_EXCEEDED, SESSION_NOT_READY
from app.models.scenario import ScenarioRun
from app.models.session import LearningSession

# Allowed state transitions from ТП §8
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "created":   {"starting"},
    "starting":  {"active"},
    "active":    {"paused", "submitted"},
    "paused":    {"active"},
    "submitted": {"checking"},
    "checking":  {"completed", "failed"},
}


async def create_session(
    db: AsyncSession,
    user_id: UUID,
    run_id: UUID,
) -> LearningSession:
    """Create a new LearningSession in 'created' state."""
    session = LearningSession(
        run_id=run_id,
        user_id=user_id,
        status="created",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID | None = None,
) -> LearningSession | None:
    """Return a LearningSession.

    If *user_id* is supplied, the query is scoped to that owner (student view).
    Pass ``user_id=None`` for teacher/admin access.
    """
    stmt = select(LearningSession).where(LearningSession.id == session_id)
    if user_id is not None:
        stmt = stmt.where(LearningSession.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def transition_status(
    db: AsyncSession,
    session_id: UUID,
    new_status: str,
) -> LearningSession:
    """Validate and apply a status transition.

    Raises 409 SESSION_NOT_READY when the transition is not in the allowed map.
    """
    result = await db.execute(
        select(LearningSession).where(LearningSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_READY,
        )

    allowed = _ALLOWED_TRANSITIONS.get(session.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=SESSION_NOT_READY,
        )

    session.status = new_status

    # Track timestamps
    if new_status == "active" and session.started_at is None:
        session.started_at = datetime.now(UTC)
    if new_status in {"completed", "failed"}:
        session.finished_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(session)
    return session


async def request_hint(
    db: AsyncSession,
    redis: object,
    session_id: UUID,
    user_id: UUID,
    error_area: str,
) -> dict[str, object]:
    """Request a hint for the session.  Delegates to AssessmentAgent.

    Fetches the scenario title from the linked ScenarioRun before calling the
    agent so the LLM prompt can reference it.

    Raises 409 HINT_LIMIT_EXCEEDED when the agent returns the limit error.
    """
    session = await get_session(db, session_id, user_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_READY,
        )

    # Resolve scenario title for hint prompt
    run_result = await db.execute(
        select(ScenarioRun).where(ScenarioRun.id == session.run_id)
    )
    run = run_result.scalar_one_or_none()
    scenario_title: str = (
        run.generated_spec.get("legend", "неизвестный сценарий")[:120]
        if run and run.generated_spec
        else "неизвестный сценарий"
    )

    from app.agents.assessment_agent import request_hint as agent_hint  # noqa: PLC0415

    result = await agent_hint(
        session_id=str(session_id),
        user_id=str(user_id),
        scenario_id=str(session.run_id),
        scenario_title=scenario_title,
        error_area=error_area,
    )

    if result.get("error") == "HINT_LIMIT_EXCEEDED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=HINT_LIMIT_EXCEEDED,
        )

    return result
