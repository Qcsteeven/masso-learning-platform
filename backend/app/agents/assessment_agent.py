"""AssessmentAgent — Phase 4.4.

Two independent LangGraph graphs:

1. hint_graph   — check_hint_limit → (limit_exceeded→END | ok→generate_hint→END)
2. submit_graph — trigger_verification → update_neo4j → END
                  interrupt_before=["update_neo4j"]  (teacher human-in-the-loop)
"""
from __future__ import annotations

import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from app.db.neo4j import get_driver
from app.db.postgres import AsyncSessionFactory
from app.db.redis import QUEUE_VERIFICATION, get_redis, session_hints_key
from app.models.assessment import Hint

# ── State ────────────────────────────────────────────────────────────────────

class AssessmentState(TypedDict):
    session_id: str
    user_id: str
    scenario_id: str
    scenario_title: str   # used in hint prompt
    error_area: str       # used in hint prompt
    hint_count: int
    hints: list[dict[str, Any]]
    skill_updates: list[dict[str, Any]]   # for submit flow
    verification_triggered: bool
    neo4j_updated: bool
    error: str | None


# ── Lazy gateway ─────────────────────────────────────────────────────────────

def _gateway():
    from app.llm.gateway import gateway  # noqa: PLC0415
    return gateway


# ── Hint-graph nodes ─────────────────────────────────────────────────────────

async def check_hint_limit(state: AssessmentState) -> dict[str, Any]:
    """Read Redis hint counter; block if already at limit (3)."""
    redis = get_redis()
    key = session_hints_key(state["session_id"])
    raw = await redis.hget(key, "used_count")
    used = int(raw) if raw else 0

    if used >= 3:
        return {
            "hint_count": used,
            "error": "HINT_LIMIT_EXCEEDED",
        }

    return {"hint_count": used, "error": None}


async def generate_hint(state: AssessmentState) -> dict[str, Any]:
    """Generate hint text via LLM, persist to PostgreSQL, increment Redis counter."""
    gw = _gateway()
    prompt = (
        f"Дай подсказку для задания '{state['scenario_title']}'.\n"
        f"Студент совершил ошибку в области: {state['error_area']}.\n"
        "ВАЖНО: укажи только область проблемы, НЕ давай готовое решение, "
        "команду или полный ответ."
    )
    response = await gw.generate(system="Ты помощник-тьютор.", prompt=prompt)
    hint_text: str = response.text if hasattr(response, "text") else str(response)

    # Persist to PostgreSQL
    new_hint_number = state["hint_count"] + 1
    async with AsyncSessionFactory() as db:
        hint = Hint(
            session_id=uuid.UUID(state["session_id"]),
            number=new_hint_number,
            text=hint_text,
            penalty_percent=10.00,
        )
        db.add(hint)
        await db.commit()
        await db.refresh(hint)
        hint_record = {
            "id": str(hint.id),
            "number": hint.number,
            "text": hint.text,
            "penalty_percent": float(hint.penalty_percent),
        }

    # Atomically increment Redis counter
    redis = get_redis()
    key = session_hints_key(state["session_id"])
    await redis.hincrby(key, "used_count", 1)

    return {
        "hints": [*state.get("hints", []), hint_record],
        "error": None,
    }


# ── Submit-graph nodes ────────────────────────────────────────────────────────

async def trigger_verification(state: AssessmentState) -> dict[str, Any]:
    """Enqueue a verification task into Redis Stream queue:verification."""
    redis = get_redis()
    await redis.xadd(
        QUEUE_VERIFICATION,
        {
            "session_id": state["session_id"],
            "user_id": state["user_id"],
            "scenario_id": state["scenario_id"],
        },
    )
    return {"verification_triggered": True, "error": None}


async def update_neo4j(state: AssessmentState) -> dict[str, Any]:
    """Write skill updates to Neo4j HAS_SKILL edges (called after teacher review)."""
    driver = get_driver()
    async with driver.session() as neo4j_session:
        for update in state.get("skill_updates", []):
            skill_id: str = update.get("skill_id", "")
            level: float = float(update.get("level", 0.0))
            success: bool = bool(update.get("success", False))

            await neo4j_session.run(
                """
                MATCH (u:User {id: $user_id})-[r:HAS_SKILL]->(s:Skill {id: $skill_id})
                SET r.level = $level,
                    r.last_confirmed = datetime(),
                    r.success_count = CASE WHEN $success THEN coalesce(r.success_count, 0) + 1
                                          ELSE r.success_count END,
                    r.fail_count    = CASE WHEN NOT $success THEN coalesce(r.fail_count, 0) + 1
                                          ELSE r.fail_count END
                """,
                user_id=state["user_id"],
                skill_id=skill_id,
                level=level,
                success=success,
            )

    return {"neo4j_updated": True, "error": None}


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_after_limit_check(state: AssessmentState) -> str:
    return "limit_exceeded" if state.get("error") == "HINT_LIMIT_EXCEEDED" else "ok"


# ── Graph: hints ─────────────────────────────────────────────────────────────

def build_hint_graph() -> Any:
    graph = StateGraph(AssessmentState)

    graph.add_node("check_hint_limit", check_hint_limit)
    graph.add_node("generate_hint", generate_hint)

    graph.set_entry_point("check_hint_limit")
    graph.add_conditional_edges(
        "check_hint_limit",
        _route_after_limit_check,
        {"limit_exceeded": END, "ok": "generate_hint"},
    )
    graph.add_edge("generate_hint", END)

    return graph.compile()


# ── Graph: submit ─────────────────────────────────────────────────────────────

def build_submit_graph() -> Any:
    graph = StateGraph(AssessmentState)

    graph.add_node("trigger_verification", trigger_verification)
    graph.add_node("update_neo4j", update_neo4j)

    graph.set_entry_point("trigger_verification")
    graph.add_edge("trigger_verification", "update_neo4j")
    graph.add_edge("update_neo4j", END)

    # interrupt_before update_neo4j so a teacher can review before Neo4j write
    return graph.compile(interrupt_before=["update_neo4j"])


hint_graph = build_hint_graph()
submit_graph = build_submit_graph()


# ── Public API used by session_service ───────────────────────────────────────

async def request_hint(
    session_id: str,
    user_id: str,
    scenario_id: str,
    scenario_title: str,
    error_area: str,
) -> dict[str, Any]:
    """Run the hint sub-graph and return the result state."""
    initial: AssessmentState = {
        "session_id": session_id,
        "user_id": user_id,
        "scenario_id": scenario_id,
        "scenario_title": scenario_title,
        "error_area": error_area,
        "hint_count": 0,
        "hints": [],
        "skill_updates": [],
        "verification_triggered": False,
        "neo4j_updated": False,
        "error": None,
    }
    result: AssessmentState = await hint_graph.ainvoke(initial)
    return dict(result)


async def submit_session(
    session_id: str,
    user_id: str,
    scenario_id: str,
    skill_updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run the submit sub-graph (pauses before update_neo4j for teacher review)."""
    initial: AssessmentState = {
        "session_id": session_id,
        "user_id": user_id,
        "scenario_id": scenario_id,
        "scenario_title": "",
        "error_area": "",
        "hint_count": 0,
        "hints": [],
        "skill_updates": skill_updates,
        "verification_triggered": False,
        "neo4j_updated": False,
        "error": None,
    }
    result: AssessmentState = await submit_graph.ainvoke(initial)
    return dict(result)
