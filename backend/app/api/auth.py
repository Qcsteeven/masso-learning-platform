from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.auth import LoginRequest, MeResponse, RefreshResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(body: LoginRequest) -> ResponseModel[TokenResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/refresh")
async def refresh() -> ResponseModel[RefreshResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/logout")
async def logout() -> ResponseModel[None]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")

@router.get("/me")
async def me() -> ResponseModel[MeResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
