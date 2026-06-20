"""Fallback template adapter — no LLM calls required.

generate(): queries ChromaDB prompt_templates collection for a similar template;
            if ChromaDB is unavailable or no result is found, returns a canned stub.
embed():    returns a zero vector of dimension 1536 (matches text-embedding-3-small).
is_available(): always True.
"""
from __future__ import annotations

import logging

from app.llm.base import LLMAdapter, LLMResponse

_log = logging.getLogger(__name__)

_EMBED_DIM = 1536
_FALLBACK_TEXT = (
    "Шаблонный ответ недоступен. Пожалуйста, настройте LLM-провайдера "
    "или загрузите шаблоны в коллекцию prompt_templates."
)


class TemplateAdapter(LLMAdapter):
    """Provider-less adapter used as the last resort in the fallback chain."""

    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
        text = await self._query_chroma(prompt)
        return LLMResponse(text=text, model="template", provider="template")

    async def embed(self, text: str) -> list[float]:
        return [0.0] * _EMBED_DIM

    async def is_available(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _query_chroma(self, prompt: str) -> str:
        """Try to find a matching template in ChromaDB; fall back to stub."""
        try:
            from app.db.chromadb import get_chroma  # noqa: PLC0415

            client = get_chroma()
            collection = await client.get_collection("prompt_templates")
            results = await collection.query(
                query_texts=[prompt],
                n_results=1,
                include=["documents"],
            )
            docs: list[list[str]] = results.get("documents", [[]])
            if docs and docs[0]:
                return docs[0][0]
        except Exception as exc:  # noqa: BLE001
            _log.debug("TemplateAdapter: ChromaDB query failed (%s), using stub", exc)
        return _FALLBACK_TEXT
