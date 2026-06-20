from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.verification import (
    VerificationPatch,
    VerificationResultResponse,
    VerificationRunRequest,
)

router = APIRouter(prefix="/verification", tags=["verification"])

@router.post("/run")
async def run_verification(body: VerificationRunRequest) -> ResponseModel[VerificationResultResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/{result_id}")
async def get_result(result_id: UUID) -> ResponseModel[VerificationResultResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/{result_id}")
async def patch_result(result_id: UUID, body: VerificationPatch) -> ResponseModel[VerificationResultResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
