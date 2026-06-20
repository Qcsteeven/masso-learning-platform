"""Unit tests for ProfileAgent (Phase 4.2).

Neo4j driver is mocked so tests run without a running database.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.profile_agent import (
    ProfileState,
    SkillDeficit,
    build_recommendations,
    compute_deficits,
    rank_deficits,
    run_profile_agent,
)

# ---------------------------------------------------------------------------
# Helpers for building fake Neo4j rows
# ---------------------------------------------------------------------------

def _row(
    skill_id: str = "s1",
    name: str = "Skill",
    difficulty: int = 5,
    domain_code: str = "devops",
    level: int = 3,
    last_confirmed: datetime | None = None,
    success_count: int = 5,
    fail_count: int = 0,
    outgoing_requires: int = 0,
) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "name": name,
        "difficulty": difficulty,
        "domain_code": domain_code,
        "level": level,
        "last_confirmed": last_confirmed,
        "success_count": success_count,
        "fail_count": fail_count,
        "outgoing_requires": outgoing_requires,
    }


def _base_state(raw_rows: list[dict[str, Any]] | None = None) -> ProfileState:
    return ProfileState(
        user_id="user-123",
        _raw_rows=raw_rows or [],
        skill_deficits=[],
        ranked_recommendations=[],
        error=None,
    )


# ---------------------------------------------------------------------------
# compute_deficits
# ---------------------------------------------------------------------------

class TestComputeDeficits:
    @pytest.mark.asyncio
    async def test_level_too_low_is_deficit(self) -> None:
        """level=1, difficulty=5 → deficit (gap >= 2)."""
        state = _base_state([_row(level=1, difficulty=5)])
        result = await compute_deficits(state)
        assert len(result["skill_deficits"]) == 1
        d = result["skill_deficits"][0]
        assert d["current_level"] == 1
        assert d["required_level"] == 5

    @pytest.mark.asyncio
    async def test_level_at_threshold_is_not_deficit(self) -> None:
        """level=4, difficulty=5 → gap=1 < 2 → not a deficit (unless stale)."""
        # Also set last_confirmed to now so staleness doesn't trigger
        state = _base_state([_row(level=4, difficulty=5, last_confirmed=datetime.now(UTC))])
        result = await compute_deficits(state)
        assert result["skill_deficits"] == []

    @pytest.mark.asyncio
    async def test_stale_91_days_is_deficit(self) -> None:
        """last_confirmed 91 days ago → stale (> 30 day threshold) → deficit."""
        stale_dt = datetime.now(UTC) - timedelta(days=91)
        # Use level/difficulty that would NOT trigger level deficit on its own
        state = _base_state([_row(level=4, difficulty=5, last_confirmed=stale_dt)])
        result = await compute_deficits(state)
        assert len(result["skill_deficits"]) == 1
        assert "не подтверждён" in result["skill_deficits"][0]["deficit_reason"]

    @pytest.mark.asyncio
    async def test_no_last_confirmed_is_deficit(self) -> None:
        """last_confirmed=None (never confirmed) → treated as stale."""
        state = _base_state([_row(level=4, difficulty=5, last_confirmed=None)])
        result = await compute_deficits(state)
        assert len(result["skill_deficits"]) == 1

    @pytest.mark.asyncio
    async def test_recent_and_good_level_is_not_deficit(self) -> None:
        """level=5, difficulty=5, confirmed today → no deficit."""
        state = _base_state([_row(level=5, difficulty=5, last_confirmed=datetime.now(UTC))])
        result = await compute_deficits(state)
        assert result["skill_deficits"] == []

    @pytest.mark.asyncio
    async def test_empty_rows_returns_empty_deficits(self) -> None:
        state = _base_state([])
        result = await compute_deficits(state)
        assert result["skill_deficits"] == []


# ---------------------------------------------------------------------------
# rank_deficits
# ---------------------------------------------------------------------------

class TestRankDeficits:
    def _make_deficit(
        self,
        skill_id: str = "s1",
        current_level: int = 1,
        required_level: int = 5,
        last_confirmed: str | None = None,
    ) -> SkillDeficit:
        return SkillDeficit(
            skill_id=skill_id,
            name="Test Skill",
            domain="devops",
            current_level=current_level,
            required_level=required_level,
            last_confirmed=last_confirmed,
            priority="low",
            deficit_reason="test",
        )

    @pytest.mark.asyncio
    async def test_outgoing_requires_4_gives_critical(self) -> None:
        """Skill with 4+ outgoing REQUIRES edges → critical priority."""
        deficit = self._make_deficit(last_confirmed=datetime.now(UTC).isoformat())
        raw_rows = [_row(skill_id="s1", outgoing_requires=4, last_confirmed=datetime.now(UTC))]
        state = _base_state(raw_rows)
        state["skill_deficits"] = [deficit]

        result = await rank_deficits(state)
        assert result["skill_deficits"][0]["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_outgoing_requires_3_not_critical(self) -> None:
        """Skill with 3 outgoing REQUIRES edges → not critical by default."""
        deficit = self._make_deficit(
            current_level=3, required_level=4,
            last_confirmed=datetime.now(UTC).isoformat()
        )
        raw_rows = [_row(skill_id="s1", outgoing_requires=3, level=3, difficulty=4,
                        last_confirmed=datetime.now(UTC))]
        state = _base_state(raw_rows)
        state["skill_deficits"] = [deficit]

        result = await rank_deficits(state)
        assert result["skill_deficits"][0]["priority"] != "critical"

    @pytest.mark.asyncio
    async def test_very_stale_skill_gives_high(self) -> None:
        """Skill not confirmed for 91 days (very stale) → high priority."""
        very_stale = (datetime.now(UTC) - timedelta(days=91)).isoformat()
        deficit = self._make_deficit(
            current_level=4, required_level=5, last_confirmed=very_stale
        )
        raw_rows = [_row(skill_id="s1", outgoing_requires=0)]
        state = _base_state(raw_rows)
        state["skill_deficits"] = [deficit]

        result = await rank_deficits(state)
        assert result["skill_deficits"][0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_large_gap_gives_high(self) -> None:
        """Gap >= 4 → high priority."""
        recent = datetime.now(UTC).isoformat()
        deficit = self._make_deficit(current_level=1, required_level=5, last_confirmed=recent)
        raw_rows = [_row(skill_id="s1", outgoing_requires=0)]
        state = _base_state(raw_rows)
        state["skill_deficits"] = [deficit]

        result = await rank_deficits(state)
        assert result["skill_deficits"][0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_medium_gap_gives_medium(self) -> None:
        """Gap=2, not stale, outgoing < 4 → medium."""
        recent = datetime.now(UTC).isoformat()
        deficit = self._make_deficit(current_level=3, required_level=5, last_confirmed=recent)
        raw_rows = [_row(skill_id="s1", outgoing_requires=1)]
        state = _base_state(raw_rows)
        state["skill_deficits"] = [deficit]

        result = await rank_deficits(state)
        assert result["skill_deficits"][0]["priority"] == "medium"


# ---------------------------------------------------------------------------
# build_recommendations
# ---------------------------------------------------------------------------

class TestBuildRecommendations:
    def _deficit(self, skill_id: str, priority: str) -> SkillDeficit:
        return SkillDeficit(
            skill_id=skill_id,
            name=skill_id,
            domain="d",
            current_level=1,
            required_level=5,
            last_confirmed=None,
            priority=priority,  # type: ignore[arg-type]
            deficit_reason="test",
        )

    @pytest.mark.asyncio
    async def test_sorted_critical_first(self) -> None:
        deficits = [
            self._deficit("low1", "low"),
            self._deficit("high1", "high"),
            self._deficit("crit1", "critical"),
            self._deficit("med1", "medium"),
        ]
        state = _base_state()
        state["skill_deficits"] = deficits

        result = await build_recommendations(state)
        priorities = [d["priority"] for d in result["ranked_recommendations"]]
        assert priorities == ["critical", "high", "medium", "low"]


# ---------------------------------------------------------------------------
# Full agent integration (Neo4j mocked)
# ---------------------------------------------------------------------------

class TestRunProfileAgent:
    @pytest.mark.asyncio
    async def test_empty_graph_returns_empty_recommendations(self) -> None:
        """When Neo4j returns no rows the agent finishes with an empty list."""

        # Proper async iterable that yields nothing
        class _EmptyAsyncResult:
            def __aiter__(self) -> "_EmptyAsyncResult":
                return self

            async def __anext__(self) -> dict[str, Any]:
                raise StopAsyncIteration

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=_EmptyAsyncResult())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.agents.profile_agent.get_driver", return_value=mock_driver):
            state = await run_profile_agent("user-empty")

        assert state["error"] is None
        assert state["ranked_recommendations"] == []

    @pytest.mark.asyncio
    async def test_neo4j_unavailable_sets_error(self) -> None:
        """If Neo4j is unavailable the agent sets error and returns empty recommendations."""
        with patch("app.agents.profile_agent.get_driver", side_effect=RuntimeError("not init")):
            state = await run_profile_agent("user-neo4j-down")

        assert state["error"] == "neo4j_unavailable"
        assert state["ranked_recommendations"] == []

    @pytest.mark.asyncio
    async def test_deficit_skill_included_in_recommendations(self) -> None:
        """A skill with level=1, difficulty=5 appears in ranked_recommendations."""
        fake_record = {
            "skill_id": "sk-001",
            "name": "Linux Basics",
            "difficulty": 5,
            "domain_code": "devops",
            "level": 1,
            "last_confirmed": datetime.now(UTC),
            "success_count": 0,
            "fail_count": 0,
            "outgoing_requires": 0,
        }

        async def _aiter_records(self_: Any) -> Any:  # noqa: ANN401
            yield fake_record

        mock_result = MagicMock()
        mock_result.__aiter__ = _aiter_records

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session = MagicMock(return_value=mock_session)

        with patch("app.agents.profile_agent.get_driver", return_value=mock_driver):
            state = await run_profile_agent("user-with-deficit")

        assert state["error"] is None
        recs = state["ranked_recommendations"]
        assert len(recs) == 1
        assert recs[0]["skill_id"] == "sk-001"
        assert recs[0]["current_level"] == 1
        assert recs[0]["required_level"] == 5
