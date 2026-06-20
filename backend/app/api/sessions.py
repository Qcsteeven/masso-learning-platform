from uuid import UUID

from fastapi import APIRouter

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.sessions import SessionCreate, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/")
async def create_session(body: SessionCreate) -> ResponseModel[SessionResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/{session_id}")
async def get_session(session_id: UUID) -> ResponseModel[SessionResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/{session_id}/pause")
async def pause_session(session_id: UUID) -> ResponseModel[SessionResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/{session_id}/submit")
async def submit_session(session_id: UUID) -> ResponseModel[SessionResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
