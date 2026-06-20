"""Unit tests for SQLAlchemy ORM models — no database required."""
from app.models import (
    AuditLog,
    Base,
    Hint,
    LLMProvider,
    LearningSession,
    Report,
    Role,
    SandboxProfile,
    ScenarioRun,
    ScenarioTemplate,
    SecurityEvent,
    SessionEvent,
    User,
    UserRole,
    VerificationResult,
)

CANONICAL_TABLE_NAMES = {
    "users",
    "roles",
    "user_roles",
    "scenario_templates",
    "scenario_runs",
    "learning_sessions",
    "session_events",
    "hints",
    "verification_results",
    "reports",
    "llm_providers",
    "sandbox_profiles",
    "audit_logs",
    "security_events",
}


def _registered_tables() -> set[str]:
    return {m.class_.__tablename__ for m in Base.registry.mappers}


def test_all_14_tables_registered() -> None:
    registered = _registered_tables()
    assert registered == CANONICAL_TABLE_NAMES, (
        f"Table mismatch.\nExpected: {sorted(CANONICAL_TABLE_NAMES)}\nGot: {sorted(registered)}"
    )


def test_no_agent_logs_table() -> None:
    assert "agent_logs" not in _registered_tables(), "agent_logs must not exist (ТП artifact)"


def test_session_events_has_four_correlation_columns() -> None:
    cols = {c.key for c in SessionEvent.__table__.columns}
    required = {"session_id", "scenario_id", "user_id", "trace_id"}
    assert required.issubset(cols), f"Missing correlation columns: {required - cols}"


def test_hint_penalty_default() -> None:
    col = Hint.__table__.columns["penalty_percent"]
    assert float(col.default.arg) == 10.0  # type: ignore[union-attr]


def test_learning_sessions_has_trace_id() -> None:
    cols = {c.key for c in LearningSession.__table__.columns}
    assert "trace_id" in cols


def test_audit_log_has_no_updated_at() -> None:
    """AuditLog is append-only — no updated_at column."""
    cols = {c.key for c in AuditLog.__table__.columns}
    assert "updated_at" not in cols


def test_all_model_classes_importable() -> None:
    models = [
        Role, User, UserRole, LLMProvider, SandboxProfile,
        ScenarioTemplate, ScenarioRun, LearningSession, SessionEvent,
        Hint, VerificationResult, Report, AuditLog, SecurityEvent,
    ]
    for m in models:
        assert m.__tablename__ in CANONICAL_TABLE_NAMES
