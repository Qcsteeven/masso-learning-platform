"""LLM Gateway — provider-agnostic adapter with fallback chain.

Fallback order:  external (OpenAI → Anthropic)  →  local (Ollama)  →  template

Active mode is persisted in the ``llm_providers`` table and cached in memory.
``switch_mode`` acquires a short lock only to swap the cached adapter reference;
it does NOT hold the lock during the actual LLM call, so in-flight requests
complete on their original adapter without interruption.
"""
from __future__ import annotations

import asyncio
import logging

from app.llm.adapters.anthropic_adapter import AnthropicAdapter
from app.llm.adapters.ollama_adapter import OllamaAdapter
from app.llm.adapters.openai_adapter import OpenAIAdapter
from app.llm.adapters.template_adapter import TemplateAdapter
from app.llm.base import LLMAdapter, LLMResponse

_log = logging.getLogger(__name__)

# Canonical mode names stored in llm_providers.mode
_MODE_EXTERNAL = "external"
_MODE_LOCAL = "local"
_MODE_TEMPLATE = "template"

_VALID_MODES = {_MODE_EXTERNAL, _MODE_LOCAL, _MODE_TEMPLATE}


class LLMGateway:
    """Provider-agnostic LLM gateway with atomic mode switching and fallback chain.

    Usage::

        from app.llm.gateway import gateway

        response = await gateway.generate("Explain TCP handshake")
        vector   = await gateway.embed("some text")
    """

    def __init__(self) -> None:
        self._mode: str = _MODE_TEMPLATE  # safe default until DB is read
        self._lock: asyncio.Lock = asyncio.Lock()

        # Adapter singletons — constructed once, reused across calls
        self._openai = OpenAIAdapter()
        self._anthropic = AnthropicAdapter()
        self._ollama = OllamaAdapter()
        self._template = TemplateAdapter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
        """Generate text using the active adapter, falling back on error."""
        chain = self._build_chain()
        last_exc: Exception | None = None

        for adapter in chain:
            try:
                return await adapter.generate(prompt, system, **kwargs)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "LLMGateway.generate: adapter %s failed (%s: %s), trying next",
                    type(adapter).__name__,
                    type(exc).__name__,
                    exc,
                )
                last_exc = exc

        # TemplateAdapter.generate never raises, so reaching here is impossible
        # in practice — but satisfy the type checker.
        raise RuntimeError("All LLM adapters failed") from last_exc

    async def embed(self, text: str) -> list[float]:
        """Embed text using the active adapter, falling back on error."""
        chain = self._build_chain()
        last_exc: Exception | None = None

        for adapter in chain:
            try:
                return await adapter.embed(text)
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "LLMGateway.embed: adapter %s failed (%s: %s), trying next",
                    type(adapter).__name__,
                    type(exc).__name__,
                    exc,
                )
                last_exc = exc

        raise RuntimeError("All LLM adapters failed") from last_exc

    async def switch_mode(self, mode: str) -> None:
        """Atomically switch the active mode.

        The lock is held only for the duration of the assignment, so in-flight
        ``generate``/``embed`` calls on the previous adapter are never interrupted.
        """
        if mode not in _VALID_MODES:
            raise ValueError(f"Unknown mode {mode!r}; expected one of {_VALID_MODES}")
        async with self._lock:
            self._mode = mode
        _log.info("LLMGateway: mode switched to %r", mode)

    async def get_active_mode(self) -> str:
        """Return the currently active mode string."""
        async with self._lock:
            return self._mode

    async def load_mode_from_db(self) -> None:
        """Read the active provider from ``llm_providers`` and update cached mode.

        Called during application startup (lifespan). Degrades gracefully if DB
        is not yet available.
        """
        try:
            from sqlalchemy import select  # noqa: PLC0415

            from app.db.postgres import get_db  # noqa: PLC0415
            from app.models.infra import LLMProvider  # noqa: PLC0415

            async for db in get_db():
                result = await db.execute(
                    select(LLMProvider.mode)
                    .where(LLMProvider.status == "active")
                    .order_by(LLMProvider.created_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row and row in _VALID_MODES:
                    await self.switch_mode(row)
                    _log.info("LLMGateway: loaded mode %r from DB", row)
                break
        except Exception as exc:  # noqa: BLE001
            _log.warning("LLMGateway.load_mode_from_db failed (%s); keeping %r", exc, self._mode)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_chain(self) -> list[LLMAdapter]:
        """Return the ordered adapter chain for the current mode.

        Reading ``self._mode`` outside the lock is intentional: we want to
        capture the mode at call-start (atomic read on CPython) without blocking
        the caller while the previous adapter handles an in-flight request.
        """
        mode = self._mode

        if mode == _MODE_EXTERNAL:
            return [self._openai, self._anthropic, self._ollama, self._template]
        if mode == _MODE_LOCAL:
            return [self._ollama, self._template]
        # _MODE_TEMPLATE or any unknown value
        return [self._template]


# ---------------------------------------------------------------------------
# Module-level singleton — import this in routers and services
# ---------------------------------------------------------------------------
gateway = LLMGateway()
