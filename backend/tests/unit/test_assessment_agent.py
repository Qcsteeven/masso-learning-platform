"""Unit tests for AssessmentAgent hint sub-graph (Phase 4.4).

Redis, LLM Gateway, and PostgreSQL are fully mocked.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Pre-import so patch() can resolve the dotted path via sys.modules
import app.agents.assessment_agent  # noqa: F401  (side-effect import)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_redis(used_count: int) -> MagicMock:
    """Return a mock Redis client reporting *used_count* hints already used."""
    r = MagicMock()
    r.hget = AsyncMock(return_value=str(used_count) if used_count > 0 else None)
    r.hincrby = AsyncMock(return_value=used_count + 1)
    return r


def _make_gateway(hint_text: str = "Проверь синтаксис конфигурационного файла.") -> MagicMock:
    gw = MagicMock()
    gw.generate = AsyncMock(return_value=SimpleNamespace(text=hint_text))
    return gw


def _make_db_session(hint_id: str | None = None) -> MagicMock:
    """Mock AsyncSessionFactory context that returns a Hint-like ORM object."""
    hint_id = hint_id or str(uuid.uuid4())
    hint_obj = MagicMock()
    hint_obj.id = uuid.UUID(hint_id)
    hint_obj.number = 1
    hint_obj.text = "Проверь синтаксис конфигурационного файла."
    hint_obj.penalty_percent = Decimal("10.00")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", hint_obj.id)
                                     or setattr(obj, "number", 1)
                                     or setattr(obj, "text", hint_obj.text)
                                     or setattr(obj, "penalty_percent", hint_obj.penalty_percent))
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


# ── Test: 3rd hint is still allowed ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_third_hint_allowed() -> None:
    """When used_count == 2 (two hints used), a third hint MUST succeed."""
    redis = _make_redis(used_count=2)
    gw = _make_gateway()
    db_ctx = _make_db_session()

    with (
        patch("app.agents.assessment_agent.get_redis", return_value=redis),
        patch("app.agents.assessment_agent._gateway", return_value=gw),
        patch("app.agents.assessment_agent.AsyncSessionFactory", return_value=db_ctx),
    ):
        from app.agents.assessment_agent import request_hint

        result = await request_hint(
            session_id="00000000-0000-0000-0000-000000000010",
            user_id="00000000-0000-0000-0000-000000000001",
            scenario_id="00000000-0000-0000-0000-000000000002",
            scenario_title="Настройка Nginx",
            error_area="конфигурация SSL",
        )

    assert result.get("error") is None
    assert len(result.get("hints", [])) == 1
    # penalty must always be 10
    assert float(result["hints"][0]["penalty_percent"]) == 10.0
    # Redis counter must have been incremented
    redis.hincrby.assert_called_once()


# ── Test: 4th hint is rejected (limit = 3) ───────────────────────────────────

@pytest.mark.asyncio
async def test_fourth_hint_rejected() -> None:
    """When used_count == 3, any further hint request must return HINT_LIMIT_EXCEEDED."""
    redis = _make_redis(used_count=3)
    gw = _make_gateway()

    with (
        patch("app.agents.assessment_agent.get_redis", return_value=redis),
        patch("app.agents.assessment_agent._gateway", return_value=gw),
    ):
        from app.agents.assessment_agent import request_hint

        result = await request_hint(
            session_id="00000000-0000-0000-0000-000000000010",
            user_id="00000000-0000-0000-0000-000000000001",
            scenario_id="00000000-0000-0000-0000-000000000002",
            scenario_title="Настройка Nginx",
            error_area="конфигурация SSL",
        )

    assert result.get("error") == "HINT_LIMIT_EXCEEDED"
    # Gateway must NOT have been called when limit is exceeded
    gw.generate.assert_not_called()
    # Redis increment must NOT have been called
    redis.hincrby.assert_not_called()


# ── Test: penalty_percent is always 10.00 ────────────────────────────────────

@pytest.mark.asyncio
async def test_hint_penalty_is_always_ten() -> None:
    """Every generated hint must carry penalty_percent == 10.00 regardless of count."""
    for used in range(3):  # 0, 1, 2 — all should succeed with penalty=10
        redis = _make_redis(used_count=used)
        gw = _make_gateway()
        db_ctx = _make_db_session()

        with (
            patch("app.agents.assessment_agent.get_redis", return_value=redis),
            patch("app.agents.assessment_agent._gateway", return_value=gw),
            patch("app.agents.assessment_agent.AsyncSessionFactory", return_value=db_ctx),
        ):
            from app.agents.assessment_agent import request_hint

            result = await request_hint(
                session_id="00000000-0000-0000-0000-000000000010",
                user_id="00000000-0000-0000-0000-000000000001",
                scenario_id="00000000-0000-0000-0000-000000000002",
                scenario_title="Настройка Nginx",
                error_area="сеть",
            )

        assert result.get("error") is None, f"Unexpected error for used={used}: {result['error']}"
        hint = result["hints"][0]
        assert float(hint["penalty_percent"]) == 10.0, (
            f"penalty_percent must be 10.0 but got {hint['penalty_percent']} (used={used})"
        )
