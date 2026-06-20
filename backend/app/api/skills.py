from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.skills import (
    RecommendationsResponse,
    SkillCreate,
    SkillGraphResponse,
    SkillNode,
    SkillPatch,
)

router = APIRouter(prefix="/skills", tags=["skills"])

@router.get("/graph")
async def get_skill_graph() -> ResponseModel[SkillGraphResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/")
async def create_skill(body: SkillCreate) -> ResponseModel[SkillNode]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/{skill_id}")
async def patch_skill(skill_id: str, body: SkillPatch) -> ResponseModel[SkillNode]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/recommendations")
async def get_recommendations() -> ResponseModel[RecommendationsResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
