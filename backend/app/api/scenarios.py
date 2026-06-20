"""Scenarios router — Phase 4.3."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.errors import SCENARIO_NOT_VALID
from app.core.response import ResponseModel
from app.db.postgres import get_db
from app.models.user import User
from app.schemas.scenarios import (
    ScenarioGenerateRequest,
    ScenarioResponse,
    TemplateCreate,
    TemplatePatch,
    TemplatePublishResponse,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("/generate", summary="Запустить генерацию нового сценария")
async def generate_scenario(
    body: ScenarioGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ResponseModel[dict[str, object]]:
    """Invoke ScenarioAgent; returns run_id and status.

    Any authenticated user may request generation. The agent enforces
    deduplication and content validation internally.
    """
    from app.services.scenario_service import generate_scenario as svc_generate  # noqa: PLC0415

    result = await svc_generate(
        user_id=str(current_user.id),
        domain=body.domain,
        difficulty=body.difficulty,
        sandbox_profile=body.sandbox_profile,
    )

    if result["status"] == "rejected":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": SCENARIO_NOT_VALID,
                "message": result.get("error") or "Сценарий не прошёл валидацию",
            },
        )

    return ResponseModel.ok(result)  # type: ignore[return-value]


@router.post("/templates", summary="Создать шаблон сценария (methodist/admin)")
async def create_template(
    body: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles("methodist", "admin"))],
) -> ResponseModel[ScenarioResponse]:
    from app.services.scenario_service import create_template as svc_create  # noqa: PLC0415

    template = await svc_create(db, body.model_dump())
    await db.commit()
    return ResponseModel.ok(
        ScenarioResponse(
            id=template.id,
            status=template.status,
            title=template.title,
            domain=None,
        )
    )


@router.patch("/templates/{template_id}", summary="Обновить поля шаблона (methodist/admin)")
async def patch_template(
    template_id: UUID,
    body: TemplatePatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles("methodist", "admin"))],
) -> ResponseModel[ScenarioResponse]:
    from app.services.scenario_service import patch_template as svc_patch  # noqa: PLC0415

    template = await svc_patch(db, template_id, body.model_dump(exclude_none=True))
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SCENARIO_NOT_VALID)
    await db.commit()
    return ResponseModel.ok(
        ScenarioResponse(
            id=template.id,
            status=template.status,
            title=template.title,
            domain=None,
        )
    )


@router.post(
    "/templates/{template_id}/publish",
    summary="Опубликовать шаблон (methodist/admin)",
)
async def publish_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles("methodist", "admin"))],
) -> ResponseModel[TemplatePublishResponse]:
    from app.services.scenario_service import publish_template as svc_publish  # noqa: PLC0415

    template = await svc_publish(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SCENARIO_NOT_VALID)
    await db.commit()
    return ResponseModel.ok(
        TemplatePublishResponse(
            id=template.id,
            status=template.status,
            version=template.version,
        )
    )
