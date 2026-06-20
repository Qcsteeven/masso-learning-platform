from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class LearningSession(Base, TimestampMixin):
    __tablename__ = "learning_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scenario_runs.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, default=new_uuid)

    run: Mapped["ScenarioRun"] = relationship(back_populates="sessions")  # type: ignore[name-defined]
    events: Mapped[list["SessionEvent"]] = relationship(back_populates="session")
    hints: Mapped[list["Hint"]] = relationship(back_populates="session")  # type: ignore[name-defined]
    verification_results: Mapped[list["VerificationResult"]] = relationship(back_populates="session")  # type: ignore[name-defined]
    reports: Mapped[list["Report"]] = relationship(back_populates="session")  # type: ignore[name-defined]


class SessionEvent(Base):
    """Digital trace — every action, incident, hint, and check in the session."""
    __tablename__ = "session_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # Four mandatory correlation columns (ТП §5, CLAUDE.md critical rules)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    session: Mapped["LearningSession"] = relationship(back_populates="events")


from app.models.scenario import ScenarioRun  # noqa: E402, F401
