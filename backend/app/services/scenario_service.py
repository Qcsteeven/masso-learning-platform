"""Scenario service — business logic for scenario generation and template management."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scenario import ScenarioTemplate


async def generate_scenario(
    user_id: str,
    domain: str,
    difficulty: int,
    sandbox_profile: str,
) -> dict[str, object]:
    """Invoke ScenarioAgent and return a summary dict.

    Returns::

        {
            "run_id": str | None,
            "status": "published" | "rejected",
            "spec": dict,
        }
    """
    from app.agents.scenario_agent import run_scenario_agent  # noqa: PLC0415

    state = await run_scenario_agent(
        user_id=user_id,
        domain=domain,
        difficulty=difficulty,
        sandbox_profile=sandbox_profile,
    )
    return {
        "run_id": state.get("scenario_run_id"),
        "status": state.get("status", "rejected"),
        "spec": state.get("generated_spec") or {},
        "error": state.get("error"),
    }


async def create_template(db: AsyncSession, data: dict[str, object]) -> ScenarioTemplate:
    """Create and persist a new ScenarioTemplate in draft status."""
    template = ScenarioTemplate(
        title=str(data["title"]),
        legend=str(data.get("legend", "")),
        criteria=data.get("criteria") or {},
        status="draft",
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


async def get_template(db: AsyncSession, template_id: UUID) -> ScenarioTemplate | None:
    result = await db.execute(
        select(ScenarioTemplate.id, ScenarioTemplate.title, ScenarioTemplate.legend,
               ScenarioTemplate.criteria, ScenarioTemplate.status, ScenarioTemplate.version)
        .where(ScenarioTemplate.id == template_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    # Re-fetch as ORM object so callers get a proper model instance
    orm_result = await db.execute(
        select(ScenarioTemplate).where(ScenarioTemplate.id == template_id)
    )
    return orm_result.scalar_one_or_none()


async def patch_template(
    db: AsyncSession, template_id: UUID, data: dict[str, object]
) -> ScenarioTemplate | None:
    """Apply a partial update to an existing ScenarioTemplate."""
    template = await get_template(db, template_id)
    if template is None:
        return None

    if "title" in data and data["title"] is not None:
        template.title = str(data["title"])
    if "legend" in data and data["legend"] is not None:
        template.legend = str(data["legend"])
    if "criteria" in data and data["criteria"] is not None:
        template.criteria = data["criteria"]  # type: ignore[assignment]
    if "status" in data and data["status"] is not None:
        template.status = str(data["status"])

    await db.flush()
    await db.refresh(template)
    return template


async def publish_template(
    db: AsyncSession, template_id: UUID
) -> ScenarioTemplate | None:
    """Bump version and set status to 'published'."""
    template = await get_template(db, template_id)
    if template is None:
        return None

    template.status = "published"
    template.version = template.version + 1
    await db.flush()
    await db.refresh(template)
    return template
