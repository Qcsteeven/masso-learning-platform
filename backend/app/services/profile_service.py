"""Profile service — business logic for skill recommendations.

All Neo4j interaction is delegated to ProfileAgent; this service owns the
public API contract and error handling.
"""
from __future__ import annotations

import logging

from app.agents.profile_agent import SkillDeficit, run_profile_agent

_log = logging.getLogger(__name__)


async def get_recommendations(user_id: str) -> list[SkillDeficit]:
    """Invoke the ProfileAgent and return the ranked skill recommendations.

    Returns an empty list if the agent encounters a Neo4j error so callers
    degrade gracefully.
    """
    state = await run_profile_agent(user_id)

    if state.get("error"):
        _log.warning(
            "profile_service.get_recommendations: agent error for user %s — %s",
            user_id,
            state["error"],
        )
        return []

    return state.get("ranked_recommendations", [])
