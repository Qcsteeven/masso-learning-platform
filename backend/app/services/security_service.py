"""Security service — append-only writes to security_events."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import SecurityEvent


async def record_event(
    db: AsyncSession,
    event_type: str,
    severity: str = "warning",
    session_id: UUID | None = None,
    user_id: UUID | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    """Append one row to security_events. Never raises — failures are swallowed."""
    try:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
            payload=payload or {},
        )
        db.add(event)
        await db.flush()
    except Exception:  # noqa: BLE001
        # Security event recording must never break the calling flow
        pass
