from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LLMProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    mode: str
    status: str
    rate_limit: dict[str, object]


class LLMProviderPatch(BaseModel):
    mode: str | None = None
    status: str | None = None
    rate_limit: dict[str, object] | None = None


class SwitchModeRequest(BaseModel):
    provider_code: str
    new_mode: str  # external | local | template
    reason: str   # mandatory for audit log


class SandboxProfileCreate(BaseModel):
    code: str
    cpu: float = 1.0
    ram_mb: int = 512
    storage_gb: int = 5
    network_policy: str = "deny_all"


class SandboxProfilePatch(BaseModel):
    cpu: float | None = None
    ram_mb: int | None = None
    storage_gb: int | None = None
    network_policy: str | None = None


class SandboxHealthResponse(BaseModel):
    active_sessions: int
    queue_depth: dict[str, int]
    providers: list[dict[str, object]]
