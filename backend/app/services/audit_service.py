"""Audit service — append-only writes to audit_logs."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    actor_id: UUID | None,
    action: str,
    object_type: str,
    object_id: UUID | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    """Append one row to audit_logs. Never raises — failures are swallowed."""
    try:
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            payload=payload or {},
        )
        db.add(entry)
        await db.flush()
    except Exception:  # noqa: BLE001
        # Audit must never break the calling flow
        pass
