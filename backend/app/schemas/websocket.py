"""Discriminated union types for all WebSocket message payloads (ТП §9 Таблица 9)."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ── Terminal (/ws/sessions/{id}/terminal) ─────────────────────────────────

class StdinMessage(BaseModel):
    type: Literal["stdin"]
    data: str


class StdoutMessage(BaseModel):
    type: Literal["stdout"]
    data: str


class StderrMessage(BaseModel):
    type: Literal["stderr"]
    data: str


class ResizeMessage(BaseModel):
    type: Literal["resize"]
    cols: int
    rows: int


class CloseMessage(BaseModel):
    type: Literal["close"]
    code: int = 0


TerminalMessage = Annotated[
    StdinMessage | StdoutMessage | StderrMessage | ResizeMessage | CloseMessage,
    Field(discriminator="type"),
]


# ── Session events (/ws/sessions/{id}/events) ─────────────────────────────

class IncidentEvent(BaseModel):
    type: Literal["incident"]
    severity: str
    message: str
    timestamp: str


class HintEvent(BaseModel):
    type: Literal["hint"]
    number: int
    text: str
    penalty_percent: float


class WarningEvent(BaseModel):
    type: Literal["warning"]
    message: str


class SecurityEvent(BaseModel):
    type: Literal["security"]
    event_type: str
    severity: str


class CheckStatusEvent(BaseModel):
    type: Literal["check_status"]
    check: str
    passed: bool


SessionEventMessage = Annotated[
    IncidentEvent | HintEvent | WarningEvent | SecurityEvent | CheckStatusEvent,
    Field(discriminator="type"),
]


# ── Status (/ws/sessions/{id}/status) ─────────────────────────────────────

class StatusChangeEvent(BaseModel):
    type: Literal["status_change"]
    status: str
    timestamp: str


# ── Admin monitoring (/ws/admin/monitoring) ───────────────────────────────

class QueueEvent(BaseModel):
    type: Literal["queue"]
    name: str
    depth: int


class ProviderEvent(BaseModel):
    type: Literal["provider"]
    code: str
    mode: str
    status: str


class SandboxEvent(BaseModel):
    type: Literal["sandbox"]
    session_id: str
    action: str


class AlertEvent(BaseModel):
    type: Literal["alert"]
    severity: str
    message: str


MonitoringMessage = Annotated[
    QueueEvent | ProviderEvent | SandboxEvent | AlertEvent,
    Field(discriminator="type"),
]
