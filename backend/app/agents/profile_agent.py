"""ProfileAgent — LangGraph StateGraph that analyses a user's Neo4j skill graph.

Pipeline:
    fetch_skill_graph → compute_deficits → rank_deficits → build_recommendations → END

Contract:
  - READ-ONLY Neo4j access. No write transactions are opened here.
  - If Neo4j is unavailable the graph transitions directly to END with
    state["error"] = "neo4j_unavailable".
  - Returns ranked_recommendations: list of SkillDeficit sorted by priority.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

_log = logging.getLogger(__name__)


def _import_get_driver() -> object:
    """Lazy import so the module loads without neo4j installed (unit test env)."""
    from app.db.neo4j import get_driver  # noqa: PLC0415

    return get_driver


# Module-level alias used in fetch_skill_graph — patchable by tests via
#   patch("app.agents.profile_agent.get_driver", ...)
try:
    from app.db.neo4j import get_driver  # noqa: PLC0415  # pragma: no cover
except ModuleNotFoundError:  # pragma: no cover
    # neo4j package not installed; get_driver will raise at runtime
    def get_driver() -> None:  # type: ignore[misc]
        raise RuntimeError("neo4j package not installed")

# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

_PRIORITY = Literal["critical", "high", "medium", "low"]


class SkillDeficit(TypedDict):
    skill_id: str
    name: str
    domain: str
    current_level: int
    required_level: int
    last_confirmed: str | None
    priority: _PRIORITY
    deficit_reason: str


class ProfileState(TypedDict):
    user_id: str
    # Raw rows from Neo4j — populated by fetch_skill_graph
    _raw_rows: list[dict[str, object]]
    skill_deficits: list[SkillDeficit]
    ranked_recommendations: list[SkillDeficit]
    error: str | None


# ---------------------------------------------------------------------------
# Cypher query
# ---------------------------------------------------------------------------

_SKILL_QUERY = """
MATCH (u:User {user_id: $user_id})-[hs:HAS_SKILL]->(s:Skill)-[:BELONGS_TO]->(d:Domain)
OPTIONAL MATCH (s)-[:REQUIRES]->(prereq:Skill)
RETURN
    s.skill_id          AS skill_id,
    s.name              AS name,
    s.difficulty        AS difficulty,
    d.code              AS domain_code,
    hs.level            AS level,
    hs.last_confirmed   AS last_confirmed,
    hs.success_count    AS success_count,
    hs.fail_count       AS fail_count,
    count(prereq)       AS outgoing_requires
"""

# ---------------------------------------------------------------------------
# Deficit rules (ТП §4.5)
# ---------------------------------------------------------------------------

_STALE_DAYS = 30       # last_confirmed older than this → deficit
_VERY_STALE_DAYS = 90  # last_confirmed older than this → stale (affects priority)
_DEFICIT_GAP = 2       # level < difficulty - gap → deficit


def _parse_dt(value: object) -> datetime | None:
    """Coerce a Neo4j temporal or ISO string to a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            return None
    # neo4j.time.DateTime objects expose .to_native()
    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        native: datetime = to_native()
        if native.tzinfo is None:
            native = native.replace(tzinfo=UTC)
        return native
    return None


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

async def fetch_skill_graph(state: ProfileState) -> ProfileState:
    """Read the user's skill graph from Neo4j (read-only transaction)."""
    try:
        driver = get_driver()
        async with driver.session() as session:
            result = await session.run(_SKILL_QUERY, user_id=state["user_id"])
            rows: list[dict[str, object]] = [dict(record) async for record in result]

        return {**state, "_raw_rows": rows, "error": None}

    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "ProfileAgent.fetch_skill_graph: Neo4j error for user %s — %s",
            state["user_id"],
            exc,
        )
        return {**state, "_raw_rows": [], "error": "neo4j_unavailable"}


async def compute_deficits(state: ProfileState) -> ProfileState:
    """Identify deficient skills from the raw Neo4j rows."""
    now = datetime.now(UTC)
    stale_threshold = now - timedelta(days=_STALE_DAYS)

    deficits: list[SkillDeficit] = []

    for row in state.get("_raw_rows", []):
        skill_id = str(row.get("skill_id") or "")
        name = str(row.get("name") or "")
        domain = str(row.get("domain_code") or "")
        difficulty = int(row.get("difficulty") or 0)
        current_level = int(row.get("level") or 0)
        last_confirmed_raw = row.get("last_confirmed")
        last_confirmed_dt = _parse_dt(last_confirmed_raw)
        last_confirmed_iso: str | None = (
            last_confirmed_dt.isoformat() if last_confirmed_dt else None
        )

        reasons: list[str] = []

        level_deficit = current_level < difficulty - _DEFICIT_GAP
        if level_deficit:
            reasons.append(
                f"уровень {current_level} ниже необходимого {difficulty} на {difficulty - current_level}"
            )

        stale = last_confirmed_dt is None or last_confirmed_dt < stale_threshold
        if stale:
            age_desc = (
                f"{(now - last_confirmed_dt).days} дней назад"
                if last_confirmed_dt
                else "никогда"
            )
            reasons.append(f"навык не подтверждён: {age_desc}")

        if reasons:
            deficits.append(
                SkillDeficit(
                    skill_id=skill_id,
                    name=name,
                    domain=domain,
                    current_level=current_level,
                    required_level=difficulty,
                    last_confirmed=last_confirmed_iso,
                    # Placeholder priority; set in rank_deficits
                    priority="low",
                    deficit_reason="; ".join(reasons),
                )
            )

    return {**state, "skill_deficits": deficits}


async def rank_deficits(state: ProfileState) -> ProfileState:
    """Assign priority to each deficit according to ТП rules."""
    now = datetime.now(UTC)
    very_stale_threshold = now - timedelta(days=_VERY_STALE_DAYS)

    # Build outgoing_requires lookup from raw rows
    outgoing: dict[str, int] = {}
    for row in state.get("_raw_rows", []):
        sid = str(row.get("skill_id") or "")
        outgoing[sid] = int(row.get("outgoing_requires") or 0)

    ranked: list[SkillDeficit] = []
    for deficit in state.get("skill_deficits", []):
        sid = deficit["skill_id"]
        req_count = outgoing.get(sid, 0)
        current_level = deficit["current_level"]
        required_level = deficit["required_level"]
        last_confirmed_dt = _parse_dt(deficit.get("last_confirmed"))
        very_stale = last_confirmed_dt is None or last_confirmed_dt < very_stale_threshold

        if req_count >= 4:
            priority: _PRIORITY = "critical"
        elif very_stale or (required_level - current_level) >= 4:
            priority = "high"
        elif (required_level - current_level) >= 2:
            priority = "medium"
        else:
            priority = "low"

        ranked.append({**deficit, "priority": priority})

    return {**state, "skill_deficits": ranked}


async def build_recommendations(state: ProfileState) -> ProfileState:
    """Sort deficits by priority (critical → high → medium → low)."""
    _order: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    sorted_deficits = sorted(
        state.get("skill_deficits", []),
        key=lambda d: _order.get(d["priority"], 99),
    )
    return {**state, "ranked_recommendations": sorted_deficits}


# ---------------------------------------------------------------------------
# Route helper — skip processing if Neo4j was unavailable
# ---------------------------------------------------------------------------

def _route_after_fetch(state: ProfileState) -> str:
    if state.get("error") == "neo4j_unavailable":
        return END  # type: ignore[return-value]
    return "compute_deficits"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    graph: StateGraph = StateGraph(ProfileState)

    graph.add_node("fetch_skill_graph", fetch_skill_graph)
    graph.add_node("compute_deficits", compute_deficits)
    graph.add_node("rank_deficits", rank_deficits)
    graph.add_node("build_recommendations", build_recommendations)

    graph.set_entry_point("fetch_skill_graph")
    graph.add_conditional_edges("fetch_skill_graph", _route_after_fetch)
    graph.add_edge("compute_deficits", "rank_deficits")
    graph.add_edge("rank_deficits", "build_recommendations")
    graph.add_edge("build_recommendations", END)

    return graph


# Compiled graph — reused across invocations (thread-safe in async context)
profile_graph = _build_graph().compile()


async def run_profile_agent(user_id: str) -> ProfileState:
    """Entry point — invoke the compiled graph and return the final state."""
    initial: ProfileState = {
        "user_id": user_id,
        "_raw_rows": [],
        "skill_deficits": [],
        "ranked_recommendations": [],
        "error": None,
    }
    result: ProfileState = await profile_graph.ainvoke(initial)  # type: ignore[assignment]
    return result
