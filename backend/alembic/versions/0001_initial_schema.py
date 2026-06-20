"""Initial schema — all 14 canonical tables from ТП §5 Рис. 21.

Revision ID: 0001
Revises:
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── 1. roles ──────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )

    # ── 2. users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ── 3. user_roles ─────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 4. llm_providers ──────────────────────────────────────────────────
    op.create_table(
        "llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("rate_limit", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_llm_providers_code"),
    )

    # ── 5. sandbox_profiles ───────────────────────────────────────────────
    op.create_table(
        "sandbox_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("cpu", sa.Numeric(), nullable=False, server_default="1"),
        sa.Column("ram_mb", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("storage_gb", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("network_policy", sa.String(64), nullable=False, server_default="deny_all"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_sandbox_profiles_code"),
    )

    # ── 6. scenario_templates ─────────────────────────────────────────────
    op.create_table(
        "scenario_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("legend", sa.Text(), nullable=False, server_default=""),
        sa.Column("criteria", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 7. scenario_runs ──────────────────────────────────────────────────
    op.create_table(
        "scenario_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("generated_spec", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 8. learning_sessions ──────────────────────────────────────────────
    op.create_table(
        "learning_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scenario_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_learning_sessions_user_id", "learning_sessions", ["user_id"])
    op.create_index("ix_learning_sessions_status", "learning_sessions", ["status"])

    # ── 9. session_events ─────────────────────────────────────────────────
    # Four mandatory correlation columns (ТП, CLAUDE.md critical rules)
    op.create_table(
        "session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="info"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_session_events_session_id", "session_events", ["session_id"])
    op.create_index("ix_session_events_trace_id", "session_events", ["trace_id"])

    # ── 10. hints ─────────────────────────────────────────────────────────
    op.create_table(
        "hints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("penalty_percent", sa.Numeric(5, 2), nullable=False, server_default="10.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 11. verification_results ──────────────────────────────────────────
    op.create_table(
        "verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("checks", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("errors", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 12. reports ───────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verification_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("format", sa.String(16), nullable=False, server_default="json"),
        sa.Column("period_from", sa.String(32), nullable=True),
        sa.Column("period_to", sa.String(32), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ── 13. audit_logs ────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        # No updated_at — append-only
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_object_type", "audit_logs", ["object_type"])

    # ── 14. security_events ───────────────────────────────────────────────
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="warning"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        # No updated_at — append-only
    )
    op.create_index("ix_security_events_session_id", "security_events", ["session_id"])
    op.create_index("ix_security_events_severity", "security_events", ["severity"])


def downgrade() -> None:
    # Drop in reverse FK order
    op.drop_table("security_events")
    op.drop_table("audit_logs")
    op.drop_table("reports")
    op.drop_table("verification_results")
    op.drop_table("hints")
    op.drop_table("session_events")
    op.drop_table("learning_sessions")
    op.drop_table("scenario_runs")
    op.drop_table("scenario_templates")
    op.drop_table("sandbox_profiles")
    op.drop_table("llm_providers")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
