"""OpenAI adapter — uses httpx directly (no openai SDK dependency).

Endpoints:
  generate → POST https://api.openai.com/v1/chat/completions
  embed    → POST https://api.openai.com/v1/embeddings  (text-embedding-3-small, dim=1536)
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.llm.base import LLMAdapter, LLMResponse

_log = logging.getLogger(__name__)

_BASE_URL = "https://api.openai.com"
_CHAT_MODEL = "gpt-4o-mini"
_EMBED_MODEL = "text-embedding-3-small"
_EMBED_DIM = 1536
_TIMEOUT = 60.0


class OpenAIAdapter(LLMAdapter):
    """Calls OpenAI REST API over httpx; no openai Python package required."""

    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        model: str = str(kwargs.get("model", _CHAT_MODEL))
        payload: dict[str, object] = {"model": model, "messages": messages}

        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
            response = await client.post(
                "/v1/chat/completions",
                json=payload,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            data = response.json()

        text: str = data["choices"][0]["message"]["content"]
        used_model: str = data.get("model", model)
        return LLMResponse(text=text, model=used_model, provider="openai")

    async def embed(self, text: str) -> list[float]:
        payload: dict[str, object] = {
            "model": _EMBED_MODEL,
            "input": text,
            "dimensions": _EMBED_DIM,
        }
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
            response = await client.post(
                "/v1/embeddings",
                json=payload,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            data = response.json()

        return data["data"][0]["embedding"]  # type: ignore[no-any-return]

    async def is_available(self) -> bool:
        key = settings.openai_api_key.get_secret_value()
        return bool(key and key.strip())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"}
