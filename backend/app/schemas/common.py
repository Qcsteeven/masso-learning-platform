from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


class ResponseModel[T](BaseModel):  # noqa: UP046 — kept for pydantic v2 generic support
    model_config = ConfigDict(from_attributes=True)

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str
    data: T | None = None
    error: ErrorDetail | None = None

    @classmethod
    def ok(cls, data: T, request_id: str | None = None) -> "ResponseModel[T]":
        return cls(request_id=request_id or str(uuid4()), status="success", data=data)

    @classmethod
    def fail(cls, code: str, message: str, details: dict[str, object] | None = None) -> "ResponseModel[object]":
        return cls(  # type: ignore[return-value]
            status="error",
            error=ErrorDetail(code=code, message=message, details=details),
        )
