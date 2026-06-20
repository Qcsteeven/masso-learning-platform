"""Sessions router — Phase 4.4 + Phase 5.3 (terminal token)."""
from __future__ import annotations

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.errors import SESSION_NOT_READY
from app.core.response import ResponseModel
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models.user import User
from app.schemas.sessions import HintRequest, SessionCreate, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/", summary="Создать учебную сессию")
async def create_session(
    body: SessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[SessionResponse]:
    from app.services.session_service import create_session as svc_create  # noqa: PLC0415

    session = await svc_create(db, user_id=current_user.id, run_id=body.run_id)
    await db.commit()
    return ResponseModel.ok(SessionResponse.model_validate(session))


@router.get("/{session_id}", summary="Получить учебную сессию")
async def get_session(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[SessionResponse]:
    from app.services.session_service import get_session as svc_get  # noqa: PLC0415
    from app.services.user_service import get_user_roles  # noqa: PLC0415

    user_roles = await get_user_roles(db, current_user.id)
    # Teachers and admins can view any session; students only their own
    owner_filter = (
        None if any(r in user_roles for r in ("teacher", "admin", "sysadmin"))
        else current_user.id
    )
    session = await svc_get(db, session_id, owner_filter)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_READY)
    return ResponseModel.ok(SessionResponse.model_validate(session))


@router.post("/{session_id}/pause", summary="Поставить сессию на паузу")
async def pause_session(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[SessionResponse]:
    from app.services.session_service import get_session, transition_status  # noqa: PLC0415

    # Ensure ownership before pausing
    session = await get_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_READY)

    updated = await transition_status(db, session_id, "paused")
    await db.commit()
    return ResponseModel.ok(SessionResponse.model_validate(updated))


@router.post("/{session_id}/submit", summary="Отправить сессию на проверку")
async def submit_session(
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[SessionResponse]:
    from app.services.session_service import get_session, transition_status  # noqa: PLC0415

    session = await get_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_READY)

    updated = await transition_status(db, session_id, "submitted")
    await db.commit()

    # Enqueue verification via AssessmentAgent
    from app.agents.assessment_agent import submit_session as agent_submit  # noqa: PLC0415

    await agent_submit(
        session_id=str(session_id),
        user_id=str(current_user.id),
        scenario_id=str(session.run_id),
        skill_updates=[],
    )

    return ResponseModel.ok(SessionResponse.model_validate(updated))


@router.post("/{session_id}/terminal-token", summary="Выпустить одноразовый токен для WebSocket-терминала")
async def get_terminal_token(
    session_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[object, Depends(get_redis)],
) -> ResponseModel[dict[str, object]]:
    """Issue a one-time short-lived token for WebSocket terminal authentication.

    The token is stored in Redis with TTL=60 s and consumed on first use by the
    ``/ws/sessions/{id}/terminal`` handler.  Ownership of the session is **not**
    verified here — the sandbox only exists for active sessions, so an invalid
    ``session_id`` simply yields no container when the WS handler tries to attach.
    """
    token = secrets.token_urlsafe(32)
    await redis.set(f"terminal_token:{token}", str(session_id), ex=60)  # type: ignore[union-attr]
    return ResponseModel.ok({"token": token, "expires_in": 60})


@router.post("/{session_id}/hint", summary="Запросить подсказку")
async def request_hint(
    session_id: UUID,
    body: HintRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles("student"))],
) -> ResponseModel[dict[str, object]]:
    from app.db.redis import get_redis  # noqa: PLC0415
    from app.services.session_service import request_hint as svc_hint  # noqa: PLC0415

    redis = get_redis()
    result = await svc_hint(
        db=db,
        redis=redis,
        session_id=session_id,
        user_id=current_user.id,
        error_area=body.error_area,
    )
    return ResponseModel.ok(result)  # type: ignore[return-value]
