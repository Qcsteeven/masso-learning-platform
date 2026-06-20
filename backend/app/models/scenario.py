from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class ScenarioTemplate(Base, TimestampMixin):
    __tablename__ = "scenario_templates"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    skill_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    legend: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    runs: Mapped[list["ScenarioRun"]] = relationship(back_populates="template")


class ScenarioRun(Base, TimestampMixin):
    __tablename__ = "scenario_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    template_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scenario_templates.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    generated_spec: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")

    template: Mapped["ScenarioTemplate"] = relationship(back_populates="runs")
    sessions: Mapped[list["LearningSession"]] = relationship(back_populates="run")  # noqa: F821
