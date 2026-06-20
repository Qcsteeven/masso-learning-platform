from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    status: str = "active"


class UserPatch(BaseModel):
    full_name: str | None = None
    status: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str
    status: str
    roles: list[str] = []


class RoleAssignment(BaseModel):
    role_codes: list[str]
