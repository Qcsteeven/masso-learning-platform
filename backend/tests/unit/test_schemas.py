"""Unit tests for Pydantic schemas — no database or HTTP required."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest
from app.schemas.reports import ReportListRequest
from app.schemas.sessions import SessionStatus
from app.schemas.websocket import MonitoringMessage, SessionEventMessage


def test_session_status_has_exactly_8_values() -> None:
    assert len(SessionStatus) == 8
    expected = {"created", "starting", "active", "paused", "submitted", "checking", "completed", "failed"}
    assert {s.value for s in SessionStatus} == expected


def test_report_list_request_requires_both_dates() -> None:
    with pytest.raises(ValidationError):
        ReportListRequest(from_date=datetime.now(UTC))  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        ReportListRequest(to_date=datetime.now(UTC))  # type: ignore[call-arg]


def test_report_list_request_date_order() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="from_date must be before to_date"):
        ReportListRequest(
            from_date=now,
            to_date=datetime(2000, 1, 1, tzinfo=UTC),
        )


def test_report_list_request_valid() -> None:
    r = ReportListRequest(
        from_date=datetime(2026, 1, 1, tzinfo=UTC),
        to_date=datetime(2026, 12, 31, tzinfo=UTC),
    )
    assert r.from_date < r.to_date


def test_login_request_valid() -> None:
    r = LoginRequest(email="admin@masso.example.com", password="secret")
    assert r.email == "admin@masso.example.com"


def test_login_request_invalid_email() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="secret")


def test_session_event_message_discriminated_union() -> None:
    from pydantic import TypeAdapter
    ta: TypeAdapter[SessionEventMessage] = TypeAdapter(SessionEventMessage)  # type: ignore[valid-type]
    payload = {"type": "incident", "severity": "critical", "message": "test", "timestamp": "now"}
    event = ta.validate_python(payload)
    assert event.type == "incident"  # type: ignore[union-attr]


def test_monitoring_message_discriminated_union() -> None:
    from pydantic import TypeAdapter
    ta: TypeAdapter[MonitoringMessage] = TypeAdapter(MonitoringMessage)  # type: ignore[valid-type]
    payload = {"type": "queue", "name": "scenario_generation", "depth": 3}
    msg = ta.validate_python(payload)
    assert msg.type == "queue"  # type: ignore[union-attr]


def test_all_schemas_importable() -> None:
    from app.schemas import (
        ErrorDetail,
        ResponseModel,
        SessionStatus,
    )
    assert ErrorDetail is not None
    assert ResponseModel is not None
    assert SessionStatus is not None
