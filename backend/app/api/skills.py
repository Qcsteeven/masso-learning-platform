"""Skills router.

GET  /skills/graph            — skill graph (nodes + edges) from Neo4j
GET  /skills/recommendations  — ranked deficit list for the current user (ProfileAgent)
POST /skills/                 — create skill  [methodist/admin — stub 501]
PATCH /skills/{skill_id}      — update skill  [methodist/admin — stub 501]
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from app.core.deps import get_current_user, require_roles
from app.core.errors import NOT_IMPLEMENTED
from app.core.response import ResponseModel
from app.db.neo4j import get_neo4j
from app.models.user import User
from app.schemas.skills import (
    RecommendationItem,
    RecommendationsResponse,
    SkillCreate,
    SkillGraphResponse,
    SkillNode,
    SkillPatch,
)

router = APIRouter(prefix="/skills", tags=["skills"])
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

_GRAPH_QUERY = """
MATCH (s:Skill)-[:BELONGS_TO]->(d:Domain)
OPTIONAL MATCH (s)-[:REQUIRES]->(prereq:Skill)
RETURN
    s.skill_id    AS skill_id,
    s.name        AS name,
    s.difficulty  AS difficulty,
    s.status      AS status,
    d.code        AS domain_code,
    collect(prereq.skill_id) AS prerequisites
"""

_EDGES_QUERY = """
MATCH (a:Skill)-[:REQUIRES]->(b:Skill)
RETURN a.skill_id AS source, b.skill_id AS target, 'REQUIRES' AS type
"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/graph")
async def get_skill_graph(
    _current_user: Annotated[User, Depends(get_current_user)],
    driver: Annotated[AsyncDriver, Depends(get_neo4j)],
) -> ResponseModel[SkillGraphResponse]:
    """Return all Skill nodes and REQUIRES edges from Neo4j."""
    async with driver.session() as session:
        nodes_result = await session.run(_GRAPH_QUERY)
        nodes_records = [dict(r) async for r in nodes_result]

        edges_result = await session.run(_EDGES_QUERY)
        edges_records = [dict(r) async for r in edges_result]

    nodes = [
        SkillNode(
            skill_id=str(r["skill_id"]),
            name=str(r["name"]),
            difficulty=int(r["difficulty"]),
            status=str(r.get("status") or "draft"),
            domain_code=str(r["domain_code"]) if r.get("domain_code") else None,
            prerequisites=[str(p) for p in (r.get("prerequisites") or []) if p],
        )
        for r in nodes_records
    ]

    edges: list[dict[str, object]] = [
        {"source": str(r["source"]), "target": str(r["target"]), "type": str(r["type"])}
        for r in edges_records
    ]

    return ResponseModel.ok(SkillGraphResponse(nodes=nodes, edges=edges))


@router.get("/recommendations")
async def get_recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[RecommendationsResponse]:
    """Return ranked skill deficit list for the authenticated user."""
    from app.services.profile_service import get_recommendations as svc_get  # noqa: PLC0415

    deficits = await svc_get(str(current_user.id))

    items = [
        RecommendationItem(
            skill_id=d["skill_id"],
            name=d["name"],
            priority=d["priority"],
            deficit_reason=d["deficit_reason"],
        )
        for d in deficits
    ]

    return ResponseModel.ok(
        RecommendationsResponse(user_id=str(current_user.id), deficits=items)
    )


@router.post("/")
async def create_skill(
    body: SkillCreate,
    _current_user: Annotated[User, Depends(require_roles("methodist", "admin"))],
) -> ResponseModel[SkillNode]:
    # methodist/admin — full implementation in Phase 5
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]


@router.patch("/{skill_id}")
async def patch_skill(
    skill_id: str,
    body: SkillPatch,
    _current_user: Annotated[User, Depends(require_roles("methodist", "admin"))],
) -> ResponseModel[SkillNode]:
    # methodist/admin — full implementation in Phase 5
    return ResponseModel.fail(NOT_IMPLEMENTED, "Не реализовано")  # type: ignore[return-value]
