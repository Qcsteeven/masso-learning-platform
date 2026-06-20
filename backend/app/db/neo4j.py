from collections.abc import AsyncGenerator

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.core.config import settings

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    if _driver is None:
        raise RuntimeError("Neo4j driver not initialised — call init_neo4j() first")
    return _driver


async def init_neo4j() -> None:
    global _driver
    _driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    await check_neo4j()


async def close_neo4j() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None


async def check_neo4j() -> None:
    """Startup check — raises if Neo4j is unreachable."""
    async with get_driver().session() as s:
        await s.run("RETURN 1")


async def get_neo4j() -> AsyncGenerator[AsyncDriver]:
    yield get_driver()
