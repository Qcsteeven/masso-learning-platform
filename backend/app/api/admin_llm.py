from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.admin import LLMProviderPatch, LLMProviderResponse, SwitchModeRequest

router = APIRouter(prefix="/admin/llm", tags=["admin"])

@router.get("/providers")
async def list_providers() -> ResponseModel[list[LLMProviderResponse]]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/providers/{provider_id}")
async def patch_provider(provider_id: UUID, body: LLMProviderPatch) -> ResponseModel[LLMProviderResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/switch-mode")
async def switch_mode(body: SwitchModeRequest) -> ResponseModel[LLMProviderResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
