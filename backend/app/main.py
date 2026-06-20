from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # DB startup checks will be wired here in Phase 1.3
    yield
    # Cleanup goes here


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
