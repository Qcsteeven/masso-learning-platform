import logging as _logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin_llm import router as admin_llm_router
from app.api.admin_sandbox import router as admin_sandbox_router
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.reports import router as reports_router
from app.api.scenarios import router as scenarios_router
from app.api.sessions import router as sessions_router
from app.api.skills import router as skills_router
from app.api.users import router as users_router
from app.api.verification import router as verification_router
from app.api.ws import router as ws_router
from app.core.config import settings

_log = _logging.getLogger(__name__)


async def _try(name: str, coro: object) -> None:
    """Run a coroutine; log warning on any error (import or runtime)."""
    try:
        await coro  # type: ignore[misc]
        _log.info("✓ %s connected", name)
    except Exception as exc:
        _log.warning("⚠  %s unavailable — degraded mode (%s: %s)", name, type(exc).__name__, exc)


async def _init_postgres() -> None:
    from app.db.postgres import check_postgres
    await check_postgres()


async def _init_neo4j() -> None:
    from app.db.neo4j import init_neo4j
    from app.db.neo4j_schema import ensure_neo4j_constraints
    await init_neo4j()
    await ensure_neo4j_constraints()


async def _init_chromadb() -> None:
    from app.db.chromadb import init_chromadb
    await init_chromadb()


async def _init_redis() -> None:
    from app.db.redis import init_redis
    await init_redis()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    await _try("PostgreSQL", _init_postgres())
    await _try("Neo4j", _init_neo4j())
    await _try("ChromaDB", _init_chromadb())
    await _try("Redis", _init_redis())

    yield

    try:
        from app.db.neo4j import close_neo4j
        await close_neo4j()
    except Exception:
        pass
    try:
        from app.db.redis import close_redis
        await close_redis()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="МАССО — Мультиагентная система ситуативного обучения",
        description="REST API + WebSocket. Версии: ТЗ §4 / ТП §9.",
        version=settings.app_version,
        docs_url="/docs",   # всегда доступен для разработки
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(skills_router)
    app.include_router(scenarios_router)
    app.include_router(sessions_router)
    app.include_router(events_router)
    app.include_router(verification_router)
    app.include_router(reports_router)
    app.include_router(admin_llm_router)
    app.include_router(admin_sandbox_router)
    app.include_router(ws_router)

    return app


app = create_app()
