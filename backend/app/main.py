from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # ── DB startup ─────────────────────────────────────────────────────────
    from app.db.chromadb import init_chromadb
    from app.db.neo4j import init_neo4j
    from app.db.neo4j_schema import ensure_neo4j_constraints
    from app.db.postgres import check_postgres
    from app.db.redis import init_redis

    await check_postgres()
    await init_neo4j()
    await ensure_neo4j_constraints()
    await init_chromadb()
    await init_redis()

    yield

    # ── DB shutdown ────────────────────────────────────────────────────────
    from app.db.neo4j import close_neo4j
    from app.db.redis import close_redis

    await close_neo4j()
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="МАССО API",
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.include_router(health_router)

    return app


app = create_app()
