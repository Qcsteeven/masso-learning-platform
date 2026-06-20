from pydantic import BaseModel


class SkillNode(BaseModel):
    skill_id: str
    name: str
    difficulty: int
    status: str
    domain_code: str | None = None
    prerequisites: list[str] = []


class SkillGraphResponse(BaseModel):
    nodes: list[SkillNode]
    edges: list[dict[str, object]]


class SkillCreate(BaseModel):
    name: str
    difficulty: int
    status: str = "draft"
    domain_code: str | None = None


class SkillPatch(BaseModel):
    name: str | None = None
    difficulty: int | None = None
    status: str | None = None


class RecommendationItem(BaseModel):
    skill_id: str
    name: str
    priority: str  # critical | high | medium | low
    deficit_reason: str


class RecommendationsResponse(BaseModel):
    user_id: str
    deficits: list[RecommendationItem]
