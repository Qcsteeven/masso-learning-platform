from uuid import UUID

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class LLMProvider(Base, TimestampMixin):
    __tablename__ = "llm_providers"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)  # external | local | template
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    rate_limit: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class SandboxProfile(Base, TimestampMixin):
    __tablename__ = "sandbox_profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    cpu: Mapped[float] = mapped_column(Numeric, nullable=False, default=1.0)
    ram_mb: Mapped[int] = mapped_column(nullable=False, default=512)
    storage_gb: Mapped[int] = mapped_column(nullable=False, default=5)
    network_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="deny_all")
