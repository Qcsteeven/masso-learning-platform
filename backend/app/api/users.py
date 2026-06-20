from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.users import RoleAssignment, UserCreate, UserPatch, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users() -> ResponseModel[list[UserResponse]]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/")
async def create_user(body: UserCreate) -> ResponseModel[UserResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.patch("/{user_id}")
async def patch_user(user_id: UUID, body: UserPatch) -> ResponseModel[UserResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.put("/{user_id}/roles")
async def assign_roles(user_id: UUID, body: RoleAssignment) -> ResponseModel[UserResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
