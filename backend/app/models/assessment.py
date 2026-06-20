from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class Hint(Base, TimestampMixin):
    __tablename__ = "hints"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    penalty_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=10.00
    )

    session: Mapped["LearningSession"] = relationship(back_populates="hints")  # type: ignore[name-defined]


class VerificationResult(Base, TimestampMixin):
    __tablename__ = "verification_results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    checks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    errors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    session: Mapped["LearningSession"] = relationship(back_populates="verification_results")  # type: ignore[name-defined]
    reports: Mapped[list["Report"]] = relationship(back_populates="verification")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    verification_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("verification_results.id", ondelete="SET NULL"), nullable=True
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="json")
    period_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    period_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["LearningSession"] = relationship(back_populates="reports")  # type: ignore[name-defined]
    verification: Mapped["VerificationResult | None"] = relationship(back_populates="reports")


from app.models.session import LearningSession  # noqa: E402, F401
