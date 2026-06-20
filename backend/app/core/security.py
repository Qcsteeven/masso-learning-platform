"""Security utilities: password hashing, JWT creation/verification."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* (per-call random salt, cost=12)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed* bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT tokens ────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": user_id,
        "roles": roles,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token() -> str:
    """Return a cryptographically random opaque refresh token (URL-safe, 32 bytes)."""
    return secrets.token_urlsafe(32)


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT access token.

    Raises ``HTTPException(401)`` when the token is invalid or expired.
    """
    try:
        payload: dict[str, object] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("sub") is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен: отсутствует sub",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
