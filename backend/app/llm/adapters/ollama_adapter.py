"""Ollama adapter — uses httpx against a local Ollama server.

Endpoints (relative to settings.ollama_base_url):
  generate     → POST /api/generate
  embed        → POST /api/embeddings
  is_available → GET  /api/version  (2-second timeout)
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.llm.base import LLMAdapter, LLMResponse

_log = logging.getLogger(__name__)

_DEFAULT_MODEL = "llama3.2"
_EMBED_MODEL = "nomic-embed-text"
_TIMEOUT = 120.0
_AVAILABILITY_TIMEOUT = 2.0


class OllamaAdapter(LLMAdapter):
    """Calls a locally-running Ollama instance over httpx."""

    @property
    def _base_url(self) -> str:
        return settings.ollama_base_url.rstrip("/")

    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
        model: str = str(kwargs.get("model", _DEFAULT_MODEL))
        payload: dict[str, object] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        text: str = data["response"]
        return LLMResponse(text=text, model=model, provider="ollama")

    async def embed(self, text: str) -> list[float]:
        model: str = _EMBED_MODEL
        payload: dict[str, object] = {"model": model, "prompt": text}

        async with httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT) as client:
            response = await client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()

        return data["embedding"]  # type: ignore[no-any-return]

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=_AVAILABILITY_TIMEOUT
            ) as client:
                response = await client.get("/api/version")
                return response.status_code == 200
        except Exception:  # noqa: BLE001
            return False
