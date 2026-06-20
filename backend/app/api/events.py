from uuid import UUID

from fastapi import APIRouter, Query

from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.schemas.events import SessionEventResponse

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/")
async def list_events(session_id: UUID = Query(...)) -> ResponseModel[list[SessionEventResponse]]:  # noqa: B008
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.post("/")
async def record_event(body: SessionEventResponse) -> ResponseModel[SessionEventResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/export")
async def export_events(session_id: UUID = Query(...)) -> ResponseModel[str]:  # noqa: B008
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
