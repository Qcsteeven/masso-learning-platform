import chromadb
from chromadb import AsyncClientAPI

from app.core.config import settings

_client: AsyncClientAPI | None = None

# Five required collections from ТП §5, architect.md
COLLECTIONS = [
    "scenario_legends",
    "knowledge_docs",
    "hint_examples",
    "prompt_templates",
    "accepted_solutions",
]


def get_chroma() -> AsyncClientAPI:
    if _client is None:
        raise RuntimeError("ChromaDB client not initialised — call init_chromadb() first")
    return _client


async def init_chromadb() -> None:
    global _client
    _client = await chromadb.AsyncHttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    await _ensure_collections()


async def _ensure_collections() -> None:
    """Create the 5 canonical collections if they don't exist yet."""
    client = get_chroma()
    existing = {c.name for c in await client.list_collections()}
    for name in COLLECTIONS:
        if name not in existing:
            await client.create_collection(name=name)


async def check_chromadb() -> None:
    """Startup check — raises if ChromaDB is unreachable."""
    client = get_chroma()
    names = {c.name for c in await client.list_collections()}
    assert set(COLLECTIONS).issubset(names), f"Missing ChromaDB collections: {set(COLLECTIONS) - names}"
