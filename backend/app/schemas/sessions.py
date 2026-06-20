from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionStatus(str, Enum):  # noqa: UP042
    """Eight canonical session states from ТП §8 / architect.md."""
    created   = "created"
    starting  = "starting"
    active    = "active"
    paused    = "paused"
    submitted = "submitted"
    checking  = "checking"
    completed = "completed"
    failed    = "failed"


class SessionCreate(BaseModel):
    run_id: UUID


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    user_id: UUID
    status: SessionStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trace_id: UUID
