from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.scenarios import (
    ScenarioGenerateRequest,
    ScenarioResponse,
    TemplateCreate,
    TemplatePatch,
    TemplatePublishResponse,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

@router.post("/generate")
async def generate_scenario(body: ScenarioGenerateRequest) -> ResponseModel[ScenarioResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/templates")
async def create_template(body: TemplateCreate) -> ResponseModel[ScenarioResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/templates/{template_id}")
async def patch_template(template_id: UUID, body: TemplatePatch) -> ResponseModel[ScenarioResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/templates/{template_id}/publish")
async def publish_template(template_id: UUID) -> ResponseModel[TemplatePublishResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
