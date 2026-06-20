"""Users router — admin-only CRUD and role management."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.response import ResponseModel
from app.db.postgres import get_db
from app.models.user import User
from app.schemas.users import RoleAssignment, UserCreate, UserPatch, UserResponse
from app.services.audit_service import log_action
from app.services.user_service import (
    assign_roles as svc_assign_roles,
)
from app.services.user_service import (
    create_user as svc_create_user,
)
from app.services.user_service import (
    get_by_id,
    get_user_roles,
)
from app.services.user_service import (
    list_users as svc_list_users,
)

router = APIRouter(prefix="/users", tags=["users"])


def _to_response(user: User, roles: list[str]) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        status=user.status,
        roles=roles,
    )


# ── GET /users/ ───────────────────────────────────────────────────────────────

@router.get("/", dependencies=[Depends(require_roles("admin"))])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseModel[list[UserResponse]]:
    users = await svc_list_users(db)
    result = []
    for u in users:
        roles = [ur.role.code for ur in u.user_roles if ur.role is not None]
        result.append(_to_response(u, roles))
    return ResponseModel.ok(result)  # type: ignore[return-value]


# ── POST /users/ ──────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin"))])
async def create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseModel[UserResponse]:
    user = await svc_create_user(db, body)
    await db.commit()
    await db.refresh(user)
    return ResponseModel.ok(_to_response(user, []))  # type: ignore[return-value]


# ── PATCH /users/{user_id} ────────────────────────────────────────────────────

@router.patch("/{user_id}", dependencies=[Depends(require_roles("admin"))])
async def patch_user(
    user_id: UUID,
    body: UserPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseModel[UserResponse]:
    user = await get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.status is not None:
        user.status = body.status

    await db.commit()
    await db.refresh(user)
    roles = await get_user_roles(db, user.id)
    return ResponseModel.ok(_to_response(user, roles))  # type: ignore[return-value]


# ── PUT /users/{user_id}/roles ────────────────────────────────────────────────

@router.put("/{user_id}/roles")
async def assign_roles(
    user_id: UUID,
    body: RoleAssignment,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_roles("admin"))],
) -> ResponseModel[UserResponse]:
    try:
        user = await svc_assign_roles(db, user_id, body.role_codes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await log_action(
        db,
        actor_id=actor.id,
        action="role_assigned",
        object_type="user",
        object_id=user_id,
        payload={"role_codes": body.role_codes},
    )
    await db.commit()

    roles = [ur.role.code for ur in user.user_roles if ur.role is not None]
    return ResponseModel.ok(_to_response(user, roles))  # type: ignore[return-value]
