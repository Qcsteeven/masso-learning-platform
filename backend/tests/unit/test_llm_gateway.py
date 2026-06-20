"""Unit tests for LLM Gateway (Phase 4.1).

All external I/O (httpx, ChromaDB, DB) is mocked so tests run without services.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.adapters.template_adapter import _EMBED_DIM, TemplateAdapter
from app.llm.base import LLMResponse
from app.llm.gateway import _MODE_EXTERNAL, _MODE_LOCAL, _MODE_TEMPLATE, LLMGateway

# ---------------------------------------------------------------------------
# TemplateAdapter
# ---------------------------------------------------------------------------

class TestTemplateAdapter:
    @pytest.mark.asyncio
    async def test_is_available_always_true(self) -> None:
        adapter = TemplateAdapter()
        assert await adapter.is_available() is True

    @pytest.mark.asyncio
    async def test_embed_returns_zero_vector_of_correct_length(self) -> None:
        adapter = TemplateAdapter()
        vector = await adapter.embed("test text")
        assert isinstance(vector, list)
        assert len(vector) == _EMBED_DIM
        assert all(v == 0.0 for v in vector)

    @pytest.mark.asyncio
    async def test_generate_fallback_when_chroma_unavailable(self) -> None:
        """If ChromaDB raises, generate() returns a non-empty stub string."""
        adapter = TemplateAdapter()
        with patch.object(adapter, "_query_chroma", new_callable=AsyncMock) as mock_q:
            from app.llm.adapters.template_adapter import _FALLBACK_TEXT
            mock_q.return_value = _FALLBACK_TEXT
            result = await adapter.generate("test prompt")
        assert isinstance(result, LLMResponse)
        assert result.provider == "template"
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_generate_uses_chroma_result_when_available(self) -> None:
        adapter = TemplateAdapter()
        expected = "Шаблонный ответ из ChromaDB"
        with patch.object(adapter, "_query_chroma", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = expected
            result = await adapter.generate("some prompt")
        assert result.text == expected


# ---------------------------------------------------------------------------
# LLMGateway fallback chain
# ---------------------------------------------------------------------------

class TestLLMGatewayFallback:
    @pytest.mark.asyncio
    async def test_fallback_to_next_adapter_on_exception(self) -> None:
        """When the first adapter in the chain raises, gateway uses the next one."""
        gateway = LLMGateway()
        gateway._mode = _MODE_EXTERNAL  # type: ignore[attr-defined]

        expected = LLMResponse(text="fallback text", model="anthropic", provider="anthropic")

        # OpenAI fails, Anthropic succeeds
        gateway._openai.generate = AsyncMock(side_effect=RuntimeError("openai down"))  # type: ignore[method-assign]
        gateway._anthropic.generate = AsyncMock(return_value=expected)  # type: ignore[method-assign]

        result = await gateway.generate("hello")
        assert result.provider == "anthropic"
        assert result.text == "fallback text"

    @pytest.mark.asyncio
    async def test_falls_through_to_template_when_all_external_fail(self) -> None:
        gateway = LLMGateway()
        gateway._mode = _MODE_EXTERNAL  # type: ignore[attr-defined]

        template_resp = LLMResponse(text="template fallback", model="template", provider="template")

        gateway._openai.generate = AsyncMock(side_effect=RuntimeError("down"))  # type: ignore[method-assign]
        gateway._anthropic.generate = AsyncMock(side_effect=RuntimeError("down"))  # type: ignore[method-assign]
        gateway._ollama.generate = AsyncMock(side_effect=RuntimeError("down"))  # type: ignore[method-assign]
        gateway._template.generate = AsyncMock(return_value=template_resp)  # type: ignore[method-assign]

        result = await gateway.generate("hello")
        assert result.provider == "template"

    @pytest.mark.asyncio
    async def test_local_mode_uses_only_ollama_and_template(self) -> None:
        gateway = LLMGateway()
        gateway._mode = _MODE_LOCAL  # type: ignore[attr-defined]

        ollama_resp = LLMResponse(text="local answer", model="llama3.2", provider="ollama")
        gateway._ollama.generate = AsyncMock(return_value=ollama_resp)  # type: ignore[method-assign]
        # OpenAI must NOT be called in local mode
        gateway._openai.generate = AsyncMock(side_effect=AssertionError("OpenAI must not be called"))  # type: ignore[method-assign]

        result = await gateway.generate("hello")
        assert result.provider == "ollama"

    @pytest.mark.asyncio
    async def test_template_mode_skips_all_llm_adapters(self) -> None:
        gateway = LLMGateway()
        gateway._mode = _MODE_TEMPLATE  # type: ignore[attr-defined]

        template_resp = LLMResponse(text="template only", model="template", provider="template")
        gateway._template.generate = AsyncMock(return_value=template_resp)  # type: ignore[method-assign]
        gateway._openai.generate = AsyncMock(side_effect=AssertionError("must not call openai"))  # type: ignore[method-assign]
        gateway._ollama.generate = AsyncMock(side_effect=AssertionError("must not call ollama"))  # type: ignore[method-assign]

        result = await gateway.generate("hello")
        assert result.provider == "template"


# ---------------------------------------------------------------------------
# LLMGateway switch_mode
# ---------------------------------------------------------------------------

class TestLLMGatewaySwitchMode:
    @pytest.mark.asyncio
    async def test_switch_mode_changes_active_mode(self) -> None:
        gateway = LLMGateway()
        assert await gateway.get_active_mode() == _MODE_TEMPLATE

        await gateway.switch_mode(_MODE_LOCAL)
        assert await gateway.get_active_mode() == _MODE_LOCAL

        await gateway.switch_mode(_MODE_EXTERNAL)
        assert await gateway.get_active_mode() == _MODE_EXTERNAL

    @pytest.mark.asyncio
    async def test_switch_mode_rejects_unknown_mode(self) -> None:
        gateway = LLMGateway()
        with pytest.raises(ValueError, match="Unknown mode"):
            await gateway.switch_mode("bogus_mode")

    @pytest.mark.asyncio
    async def test_switch_mode_does_not_interrupt_in_flight_generate(self) -> None:
        """An in-flight generate() call completes on its original adapter even
        after switch_mode() is called from a concurrent task."""
        gateway = LLMGateway()
        gateway._mode = _MODE_TEMPLATE  # type: ignore[attr-defined]

        slow_response = LLMResponse(text="slow result", model="template", provider="template")

        generate_started = asyncio.Event()
        generate_may_finish = asyncio.Event()

        async def slow_generate(prompt: str, system: str = "", **kwargs: object) -> LLMResponse:
            generate_started.set()
            await generate_may_finish.wait()
            return slow_response

        gateway._template.generate = slow_generate  # type: ignore[method-assign]

        # Start generate in background
        task = asyncio.create_task(gateway.generate("slow prompt"))

        # Wait until generate has started, then switch mode
        await generate_started.wait()
        await gateway.switch_mode(_MODE_LOCAL)

        # Allow the in-flight generate to finish
        generate_may_finish.set()
        result = await task

        # The original (template) response must be returned intact
        assert result.text == "slow result"
        assert result.provider == "template"
        # Mode is now local
        assert await gateway.get_active_mode() == _MODE_LOCAL
