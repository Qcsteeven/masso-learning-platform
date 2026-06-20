"""Abstract base for LLM adapters used by the LLM Gateway."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str


class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str = "", **kwargs: object) -> LLMResponse: ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
