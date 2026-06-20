from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VerificationRunRequest(BaseModel):
    session_id: UUID


class VerificationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    score: float
    checks: dict[str, object]
    status: str
    errors: dict[str, object]


class VerificationPatch(BaseModel):
    score: float | None = None
    reason: str  # mandatory for audit — must be non-empty
    status: str | None = None
