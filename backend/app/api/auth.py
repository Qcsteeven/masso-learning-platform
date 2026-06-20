"""Auth router — login, refresh, logout, me."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import AUTH_INVALID_CREDENTIALS
from app.core.response import ResponseModel
from app.core.security import create_access_token, create_refresh_token
from app.db.postgres import get_db
from app.db.redis import get_redis
from app.models.user import User
from app.schemas.auth import LoginRequest, MeResponse, RefreshResponse, TokenResponse
from app.services.audit_service import log_action
from app.services.security_service import record_event
from app.services.user_service import get_user_roles, verify_credentials

router = APIRouter(prefix="/auth", tags=["auth"])

# Redis key helpers
_LOGIN_RATE_TTL = 300   # 5 minutes in seconds
_LOGIN_RATE_MAX = 5     # max attempts before lockout
_REFRESH_TTL_SEC = 7 * 24 * 3600  # 7 days


def _rate_key(email: str) -> str:
    return f"rate:{email}:login"


def _refresh_key(token: str) -> str:
    return f"rt:{token}"


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseModel[TokenResponse]:
    redis = get_redis()
    rate_key = _rate_key(body.email)

    # Check rate limit before attempting credential verification
    attempts_raw = await redis.get(rate_key)
    attempts = int(attempts_raw) if attempts_raw else 0
    if attempts >= _LOGIN_RATE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток входа. Попробуйте через 5 минут.",
        )

    user = await verify_credentials(db, body.email, body.password)

    if user is None:
        # Increment counter; set TTL only on first failure
        pipe = redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, _LOGIN_RATE_TTL)
        counts = await pipe.execute()
        new_count = int(counts[0])

        await log_action(
            db, None, "login_failed", "user", payload={"email": body.email}
        )

        if new_count >= _LOGIN_RATE_MAX:
            await record_event(
                db,
                event_type="login_brute_force",
                severity="warning",
                payload={"email": body.email, "attempts": new_count},
            )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login — reset rate counter
    await redis.delete(rate_key)

    roles = await get_user_roles(db, user.id)
    access_token = create_access_token(str(user.id), roles)
    refresh_token = create_refresh_token()

    # Store refresh token in Redis
    await redis.setex(_refresh_key(refresh_token), _REFRESH_TTL_SEC, str(user.id))

    await log_action(db, user.id, "login_success", "user", object_id=user.id)
    await db.commit()

    # Set HttpOnly cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_REFRESH_TTL_SEC,
        path="/auth",
    )

    return ResponseModel.ok(TokenResponse(access_token=access_token))  # type: ignore[return-value]


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> ResponseModel[RefreshResponse]:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
        )

    redis = get_redis()
    stored_user_id = await redis.get(_refresh_key(refresh_token))
    if not stored_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
        )

    from uuid import UUID  # noqa: PLC0415

    from app.services.user_service import get_by_id  # noqa: PLC0415

    user = await get_by_id(db, UUID(stored_user_id))
    if user is None or user.status != "active":
        await redis.delete(_refresh_key(refresh_token))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
        )

    # Rotate: delete old token, issue new one
    await redis.delete(_refresh_key(refresh_token))
    new_refresh_token = create_refresh_token()
    await redis.setex(_refresh_key(new_refresh_token), _REFRESH_TTL_SEC, str(user.id))

    roles = await get_user_roles(db, user.id)
    access_token = create_access_token(str(user.id), roles)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_REFRESH_TTL_SEC,
        path="/auth",
    )

    return ResponseModel.ok(RefreshResponse(access_token=access_token))  # type: ignore[return-value]


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> ResponseModel[None]:
    if refresh_token:
        redis = get_redis()
        await redis.delete(_refresh_key(refresh_token))

    response.delete_cookie(key="refresh_token", path="/auth")
    return ResponseModel.ok(None)


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me")
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseModel[MeResponse]:
    roles = await get_user_roles(db, current_user.id)
    data = MeResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        roles=roles,
        status=current_user.status,
    )
    return ResponseModel.ok(data)  # type: ignore[return-value]
