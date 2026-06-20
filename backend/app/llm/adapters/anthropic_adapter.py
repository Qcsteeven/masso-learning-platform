"""Anthropic adapter — uses httpx directly (no anthropic SDK dependency).

Endpoint:
  generate → POST https://api.anthropic.com/v1/messages
  embed    → Anthropic has no public embedding API; delegates to TemplateAdapter (zero vector).
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.llm.base import LLMAdapter, LLMResponse

_log = logging.getLogger(__name__)

_BASE_URL = "https://api.anthropic.com"
_DEFAULT_MODEL = "claude-3-5-haiku-20241022"
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_TOKENS = 4096
_TIMEOUT = 60.0
_EMBED_DIM = 1536


class AnthropicAdapter(LLMAdapter):
    """Calls Anthropic Messages API over httpx; no anthropic Python package required."""

    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
        model: str = str(kwargs.get("model", _DEFAULT_MODEL))
        max_tokens: int = int(kwargs.get("max_tokens", _MAX_TOKENS))  # type: ignore[arg-type]

        payload: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
            response = await client.post(
                "/v1/messages",
                json=payload,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            data = response.json()

        # Anthropic returns content as a list of blocks
        content_blocks: list[dict[str, str]] = data.get("content", [])
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        used_model: str = data.get("model", model)
        return LLMResponse(text=text, model=used_model, provider="anthropic")

    async def embed(self, text: str) -> list[float]:
        """Anthropic has no public embedding endpoint; return a zero vector."""
        _log.debug("AnthropicAdapter.embed: delegating to zero vector (no public API)")
        return [0.0] * _EMBED_DIM

    async def is_available(self) -> bool:
        key = settings.anthropic_api_key.get_secret_value()
        return bool(key and key.strip())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        return {
            "x-api-key": settings.anthropic_api_key.get_secret_value(),
            "anthropic-version": _ANTHROPIC_VERSION,
        }
