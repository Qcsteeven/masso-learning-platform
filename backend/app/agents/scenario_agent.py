"""ScenarioAgent — Phase 4.3.

LangGraph StateGraph:
  check_dedup → (rejected→END | ok→generate) → validate_achievability
  → (invalid→END | valid→publish) → END

ChromaDB cosine distance ≤ 0.10  ≡  similarity ≥ 0.90  → reject (ТП §5).
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.db.chromadb import get_chroma
from app.db.postgres import AsyncSessionFactory
from app.models.scenario import ScenarioRun

# ── State ────────────────────────────────────────────────────────────────────

class ScenarioState(TypedDict):
    user_id: str
    domain: str
    difficulty: int
    sandbox_profile: str
    dedup_result: dict[str, Any]
    generated_spec: dict[str, Any]
    validation_result: dict[str, Any]
    status: str           # "generating" | "published" | "rejected"
    scenario_run_id: str | None
    error: str | None


# ── Helpers ──────────────────────────────────────────────────────────────────

_UNSAFE = re.compile(r"[^\w\s\-.,/]", re.UNICODE)

def _sanitize(value: str) -> str:
    """Remove characters that could interfere with prompt injection."""
    return _UNSAFE.sub("", value)[:200]


def _gateway():  # lazy import so the module loads even if gateway.py is absent
    from app.llm.gateway import gateway  # noqa: PLC0415
    return gateway


# ── Node implementations ─────────────────────────────────────────────────────

async def check_dedup(state: ScenarioState) -> dict[str, Any]:
    """Query ChromaDB scenario_legends; reject if cosine distance ≤ 0.10."""
    gw = _gateway()
    embed_result: list[float] = await gw.embed(state["domain"])

    chroma = get_chroma()
    collection = await chroma.get_collection("scenario_legends")

    results = await collection.query(
        query_embeddings=[embed_result],
        n_results=1,
        where={"domain": state["domain"]},
        include=["distances", "metadatas"],
    )

    distances: list[list[float]] = results.get("distances") or [[]]
    first_distance = distances[0][0] if distances and distances[0] else 1.0

    # ChromaDB with cosine space: distance = 1 − similarity
    # threshold: similarity ≥ 0.90  →  distance ≤ 0.10
    if first_distance <= 0.10:
        ids: list[list[str]] = results.get("ids") or [[]]
        similar_id = ids[0][0] if ids and ids[0] else None
        return {
            "dedup_result": {"status": "rejected", "similar_id": similar_id},
            "status": "rejected",
            "error": "SCENARIO_NOT_VALID: дублирующий сценарий (cosine similarity ≥ 0.90)",
        }

    return {
        "dedup_result": {"status": "ok", "similar_id": None},
        "status": "generating",
        "error": None,
    }


async def generate(state: ScenarioState) -> dict[str, Any]:
    """Call LLM Gateway; parse JSON spec from response."""
    domain = _sanitize(state["domain"])
    difficulty = max(1, min(5, int(state["difficulty"])))

    system_prompt = (
        "Ты генератор учебных ИТ-сценариев. Возвращай JSON строго по схеме."
    )
    user_prompt = (
        f"Сгенерируй сценарий для домена {domain}, сложность {difficulty}/5.\n"
        "Верни JSON: {\"legend\": str, \"artifacts\": [...], \"checks\": [...], "
        "\"incidents\": [...], \"hints_policy\": {...}}"
    )

    gw = _gateway()
    response = await gw.generate(system=system_prompt, prompt=user_prompt)
    raw_text: str = response.text if hasattr(response, "text") else str(response)

    # Extract JSON block (model might wrap it in markdown fences)
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        return {
            "generated_spec": {},
            "status": "rejected",
            "error": "LLM вернул не-JSON ответ",
        }

    try:
        spec: dict[str, Any] = json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        return {
            "generated_spec": {},
            "status": "rejected",
            "error": f"Ошибка разбора JSON: {exc}",
        }

    return {"generated_spec": spec, "status": "generating", "error": None}


async def validate_achievability(state: ScenarioState) -> dict[str, Any]:
    """Validate that spec contains non-empty legend and checks."""
    spec = state.get("generated_spec") or {}
    errors: list[str] = []

    legend = spec.get("legend", "")
    if not isinstance(legend, str) or not legend.strip():
        errors.append("legend отсутствует или пустой")

    checks = spec.get("checks", [])
    if not isinstance(checks, list) or len(checks) == 0:
        errors.append("checks отсутствует или пустой список")

    if errors:
        return {
            "validation_result": {"valid": False, "errors": errors},
            "status": "rejected",
            "error": "; ".join(errors),
        }

    return {
        "validation_result": {"valid": True, "errors": []},
        "status": "generating",
        "error": None,
    }


async def publish(state: ScenarioState) -> dict[str, Any]:
    """Persist ScenarioRun to PostgreSQL and store legend embedding in ChromaDB."""
    run_id = str(uuid.uuid4())

    async with AsyncSessionFactory() as db:
        run = ScenarioRun(
            id=uuid.UUID(run_id),
            # template_id is required FK — we store a sentinel zero UUID when
            # the run is agent-generated without an explicit template.
            template_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=uuid.UUID(state["user_id"]),
            generated_spec=state["generated_spec"],
            status="published",
        )
        db.add(run)
        await db.commit()

    # Store embedding in ChromaDB so future dedup checks can find it
    gw = _gateway()
    legend_text: str = state["generated_spec"].get("legend", "")
    embed_result: list[float] = await gw.embed(legend_text)

    chroma = get_chroma()
    collection = await chroma.get_collection("scenario_legends")
    await collection.add(
        ids=[run_id],
        embeddings=[embed_result],
        documents=[legend_text],
        metadatas=[{"domain": state["domain"], "user_id": state["user_id"]}],
    )

    return {"scenario_run_id": run_id, "status": "published", "error": None}


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_after_dedup(state: ScenarioState) -> str:
    return "rejected" if state["status"] == "rejected" else "ok"


def _route_after_validate(state: ScenarioState) -> str:
    return "invalid" if state["status"] == "rejected" else "valid"


# ── Graph construction ────────────────────────────────────────────────────────

def build_scenario_graph() -> Any:
    graph = StateGraph(ScenarioState)

    graph.add_node("check_dedup", check_dedup)
    graph.add_node("generate", generate)
    graph.add_node("validate_achievability", validate_achievability)
    graph.add_node("publish", publish)

    graph.set_entry_point("check_dedup")

    graph.add_conditional_edges(
        "check_dedup",
        _route_after_dedup,
        {"rejected": END, "ok": "generate"},
    )
    graph.add_edge("generate", "validate_achievability")
    graph.add_conditional_edges(
        "validate_achievability",
        _route_after_validate,
        {"invalid": END, "valid": "publish"},
    )
    graph.add_edge("publish", END)

    return graph.compile()


# Compiled graph singleton (lazily built on first import)
scenario_graph = build_scenario_graph()


async def run_scenario_agent(
    user_id: str,
    domain: str,
    difficulty: int,
    sandbox_profile: str,
) -> ScenarioState:
    """Entry-point used by scenario_service."""
    initial: ScenarioState = {
        "user_id": user_id,
        "domain": domain,
        "difficulty": difficulty,
        "sandbox_profile": sandbox_profile,
        "dedup_result": {},
        "generated_spec": {},
        "validation_result": {},
        "status": "generating",
        "scenario_run_id": None,
        "error": None,
    }
    result: ScenarioState = await scenario_graph.ainvoke(initial)
    return result
