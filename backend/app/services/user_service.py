"""User service — all user/role business logic lives here, not in routers."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.models.user import Role, User, UserRole
from app.schemas.users import UserCreate


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Return User with eager-loaded user_roles→role, or None."""
    result = await db.execute(
        select(User)
        .where(User.email == email)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Return User with eager-loaded user_roles→role, or None."""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    return result.scalar_one_or_none()


async def get_user_roles(db: AsyncSession, user_id: UUID) -> list[str]:
    """Return list of role codes assigned to the user."""
    result = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())


async def verify_credentials(db: AsyncSession, email: str, password: str) -> User | None:
    """Return User if email+password are valid, otherwise None."""
    user = await get_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Create and persist a new User. Does not assign any roles."""
    user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(data.password),
        status=data.status,
    )
    db.add(user)
    await db.flush()  # populate user.id before returning
    await db.refresh(user, ["user_roles"])
    return user


async def assign_roles(db: AsyncSession, user_id: UUID, role_codes: list[str]) -> User:
    """Replace the user's role assignments with *role_codes*.

    Fetches role objects, removes all existing UserRole rows for the user,
    then inserts new ones. Raises ValueError if any code is unknown.
    """
    # Resolve codes to Role objects
    result = await db.execute(select(Role).where(Role.code.in_(role_codes)))
    roles = result.scalars().all()
    found_codes = {r.code for r in roles}
    missing = set(role_codes) - found_codes
    if missing:
        raise ValueError(f"Неизвестные коды ролей: {missing}")

    # Delete existing assignments
    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id)
    )
    for ur in existing.scalars().all():
        await db.delete(ur)

    # Insert new assignments
    now = datetime.now(UTC)
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id, assigned_at=now))

    await db.flush()

    user = await get_by_id(db, user_id)
    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")
    return user


async def list_users(db: AsyncSession) -> list[User]:
    """Return all users with roles eager-loaded."""
    result = await db.execute(
        select(User).options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    return list(result.scalars().all())
