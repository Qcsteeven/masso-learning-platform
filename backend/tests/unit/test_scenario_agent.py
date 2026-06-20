"""Unit tests for ScenarioAgent (Phase 4.3).

All external I/O — ChromaDB, LLM Gateway, PostgreSQL — is mocked.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Pre-import so patch() can resolve the dotted path via sys.modules
import app.agents.scenario_agent  # noqa: F401  (side-effect import)

# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _make_chroma_results(distance: float, doc_id: str = "existing-run-id") -> dict:
    """Build a ChromaDB query result dict with a single match at *distance*."""
    return {
        "ids": [[doc_id]],
        "distances": [[distance]],
        "metadatas": [[{"domain": "devops"}]],
    }


def _make_gateway(embed_return: list[float] | None = None, generate_text: str = "") -> MagicMock:
    gw = MagicMock()
    gw.embed = AsyncMock(return_value=embed_return or [0.1] * 768)
    response = SimpleNamespace(text=generate_text)
    gw.generate = AsyncMock(return_value=response)
    return gw


def _make_collection(query_result: dict) -> AsyncMock:
    coll = AsyncMock()
    coll.query = AsyncMock(return_value=query_result)
    coll.add = AsyncMock()
    return coll


def _make_chroma_client(collection: AsyncMock) -> MagicMock:
    client = MagicMock()
    client.get_collection = AsyncMock(return_value=collection)
    return client


# ── Happy-path spec used across multiple tests ────────────────────────────────

_VALID_SPEC: dict = {
    "legend": "Настрой веб-сервер Nginx с SSL-терминацией",
    "artifacts": [{"type": "config", "path": "/etc/nginx/nginx.conf"}],
    "checks": [{"id": "check_nginx", "type": "service_running", "service": "nginx"}],
    "incidents": [],
    "hints_policy": {"max_hints": 3, "penalty": 10},
}


# ── Test: dedup rejects when cosine distance ≤ 0.10 (similarity ≥ 0.90) ─────

@pytest.mark.asyncio
async def test_dedup_rejects_high_similarity() -> None:
    """Distance 0.05 → similarity 0.95 → agent must return status='rejected'."""
    gw = _make_gateway()
    collection = _make_collection(_make_chroma_results(distance=0.05))
    chroma_client = _make_chroma_client(collection)

    with (
        patch("app.agents.scenario_agent._gateway", return_value=gw),
        patch("app.agents.scenario_agent.get_chroma", return_value=chroma_client),
    ):
        from app.agents.scenario_agent import run_scenario_agent

        result = await run_scenario_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            domain="devops",
            difficulty=3,
            sandbox_profile="devops-base",
        )

    assert result["status"] == "rejected"
    assert result["dedup_result"]["status"] == "rejected"
    assert result["scenario_run_id"] is None


# ── Test: dedup passes when cosine distance > 0.10 (similarity < 0.90) ───────

@pytest.mark.asyncio
async def test_dedup_passes_low_similarity() -> None:
    """Distance 0.15 → similarity 0.85 → dedup passes, agent continues."""
    gw = _make_gateway(generate_text=json.dumps(_VALID_SPEC))
    collection = _make_collection(_make_chroma_results(distance=0.15))
    chroma_client = _make_chroma_client(collection)

    # Patch AsyncSessionFactory so publish() doesn't hit a real DB
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.agents.scenario_agent._gateway", return_value=gw),
        patch("app.agents.scenario_agent.get_chroma", return_value=chroma_client),
        patch("app.agents.scenario_agent.AsyncSessionFactory", return_value=mock_ctx),
    ):
        from app.agents.scenario_agent import run_scenario_agent

        result = await run_scenario_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            domain="devops",
            difficulty=3,
            sandbox_profile="devops-base",
        )

    assert result["dedup_result"]["status"] == "ok"


# ── Test: generate node rejects non-JSON LLM response ────────────────────────

@pytest.mark.asyncio
async def test_generate_rejects_non_json_response() -> None:
    """LLM returns plain text (no JSON) → status must be 'rejected'."""
    gw = _make_gateway(generate_text="Извините, я не могу сгенерировать сценарий.")
    collection = _make_collection(_make_chroma_results(distance=0.50))
    chroma_client = _make_chroma_client(collection)

    with (
        patch("app.agents.scenario_agent._gateway", return_value=gw),
        patch("app.agents.scenario_agent.get_chroma", return_value=chroma_client),
    ):
        from app.agents.scenario_agent import run_scenario_agent

        result = await run_scenario_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            domain="devops",
            difficulty=2,
            sandbox_profile="devops-base",
        )

    assert result["status"] == "rejected"
    assert result["scenario_run_id"] is None


# ── Test: validate_achievability rejects spec with empty checks ────────────────

@pytest.mark.asyncio
async def test_validate_rejects_empty_checks() -> None:
    """Spec with 'checks': [] must yield status='rejected'."""
    bad_spec = {**_VALID_SPEC, "checks": []}
    gw = _make_gateway(generate_text=json.dumps(bad_spec))
    collection = _make_collection(_make_chroma_results(distance=0.50))
    chroma_client = _make_chroma_client(collection)

    with (
        patch("app.agents.scenario_agent._gateway", return_value=gw),
        patch("app.agents.scenario_agent.get_chroma", return_value=chroma_client),
    ):
        from app.agents.scenario_agent import run_scenario_agent

        result = await run_scenario_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            domain="devops",
            difficulty=1,
            sandbox_profile="devops-base",
        )

    assert result["status"] == "rejected"
    assert result["validation_result"]["valid"] is False
    assert any("checks" in e for e in result["validation_result"]["errors"])


# ── Test: full happy path → status='published' ────────────────────────────────

@pytest.mark.asyncio
async def test_full_happy_path_published() -> None:
    """Full pipeline with all checks passing must produce status='published'."""
    gw = _make_gateway(generate_text=json.dumps(_VALID_SPEC))
    collection = _make_collection(_make_chroma_results(distance=0.50))
    chroma_client = _make_chroma_client(collection)

    # Mock AsyncSessionFactory context manager
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.agents.scenario_agent._gateway", return_value=gw),
        patch("app.agents.scenario_agent.get_chroma", return_value=chroma_client),
        patch("app.agents.scenario_agent.AsyncSessionFactory", return_value=mock_ctx),
    ):
        from app.agents.scenario_agent import run_scenario_agent

        result = await run_scenario_agent(
            user_id="00000000-0000-0000-0000-000000000001",
            domain="devops",
            difficulty=4,
            sandbox_profile="devops-base",
        )

    assert result["status"] == "published"
    assert result["scenario_run_id"] is not None
    assert result["validation_result"]["valid"] is True
    assert result["dedup_result"]["status"] == "ok"
    # ChromaDB add should have been called once for the legend
    collection.add.assert_called_once()
