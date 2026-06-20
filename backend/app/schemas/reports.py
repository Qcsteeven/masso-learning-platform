from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class ReportListRequest(BaseModel):
    """Both dates are required — REPORT_PERIOD_REQUIRED if either is missing."""
    from_date: datetime
    to_date: datetime

    @model_validator(mode="after")
    def check_date_order(self) -> "ReportListRequest":
        if self.from_date >= self.to_date:
            raise ValueError("from_date must be before to_date")
        return self


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    verification_id: UUID | None
    format: str
    period_from: str | None
    period_to: str | None
    file_url: str | None


class ReportExportRequest(BaseModel):
    report_id: UUID
    format: str = "json"  # pdf | csv | json
