from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScenarioGenerateRequest(BaseModel):
    domain: str
    difficulty: int
    sandbox_profile: str = "devops-base"


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    domain: str | None = None


class TemplateCreate(BaseModel):
    title: str
    domain: str
    legend: str = ""
    criteria: dict[str, object] = {}
    sandbox_profile: str = "devops-base"


class TemplatePatch(BaseModel):
    title: str | None = None
    legend: str | None = None
    criteria: dict[str, object] | None = None
    status: str | None = None


class TemplatePublishResponse(BaseModel):
    id: UUID
    status: str
    version: int
