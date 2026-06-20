from uuid import UUID

from fastapi import APIRouter, Query

from app.core.errors import NOT_IMPLEMENTED, REPORT_PERIOD_REQUIRED
from app.core.response import ResponseModel
from app.schemas.reports import ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/")
async def list_reports(
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
) -> ResponseModel[list[ReportResponse]]:
    if not from_date or not to_date:
        return ResponseModel.fail(REPORT_PERIOD_REQUIRED, "Необходимо указать период")  # type: ignore[return-value]
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/{report_id}")
async def get_report(report_id: UUID) -> ResponseModel[ReportResponse]:
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]

@router.get("/export")
async def export_report(report_id: UUID = Query(...), format: str = Query("json")) -> ResponseModel[str]:  # noqa: B008
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
