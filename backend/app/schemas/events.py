from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    scenario_id: UUID
    user_id: UUID
    trace_id: UUID
    event_type: str
    severity: str
    payload: dict[str, object]
    created_at: datetime


class EventExportRequest(BaseModel):
    session_id: UUID
    from_dt: datetime | None = None
    to_dt: datetime | None = None
    format: str = "json"  # json | csv
