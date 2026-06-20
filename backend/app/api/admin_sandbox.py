from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.admin import SandboxHealthResponse, SandboxProfileCreate, SandboxProfilePatch

router = APIRouter(prefix="/admin/sandbox", tags=["admin"])

@router.get("/profiles")
async def list_profiles() -> ResponseModel[list[dict]]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/profiles")
async def create_profile(body: SandboxProfileCreate) -> ResponseModel[dict]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/profiles/{profile_id}")
async def patch_profile(profile_id: UUID, body: SandboxProfilePatch) -> ResponseModel[dict]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/health")
async def sandbox_health() -> ResponseModel[SandboxHealthResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
