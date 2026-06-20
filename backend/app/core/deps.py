"""FastAPI dependency injection: current user resolution and RBAC guards."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AUTH_FORBIDDEN, AUTH_INVALID_CREDENTIALS
from app.core.security import decode_access_token
from app.db.postgres import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the Bearer token to a User ORM instance.

    Raises 401 if the token is invalid/expired, 401 if the user is not found,
    and 403 if the account is inactive.
    """
    payload = decode_access_token(token)  # raises 401 on bad token
    user_id: str | None = payload.get("sub")  # type: ignore[assignment]
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Import here to avoid circular imports (deps <- user_service <- deps)
    from uuid import UUID

    from app.services.user_service import get_by_id  # noqa: PLC0415

    user = await get_by_id(db, UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AUTH_FORBIDDEN,
        )
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    """Return a FastAPI dependency that enforces at least one of *roles*.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_roles("admin"))])
        async def handler(current_user: User = Depends(require_roles("admin"))) -> ...:
            ...
    """

    async def _guard(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        user = await get_current_user(token, db)

        from app.services.user_service import get_user_roles  # noqa: PLC0415

        user_roles = await get_user_roles(db, user.id)
        if not any(r in user_roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AUTH_FORBIDDEN,
            )
        return user

    return _guard  # type: ignore[return-value]
