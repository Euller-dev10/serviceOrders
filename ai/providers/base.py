from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Falha de provedor LLM (rede, chave, rate limit...)."""


@dataclass
class LLMResult:
    content: str
    provider: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    fallback: bool = False
    metadata: dict = field(default_factory=dict)


class BaseChatProvider(ABC):
    name: str = 'base'
    default_model: str = ''

    def __init__(self, model: str | None = None, **kwargs):
        self.model = model or self.default_model
        self.options = kwargs

    @abstractmethod
    def complete(self, messages: list[dict], **kwargs) -> LLMResult:
        """Recebe [{'role': ..., 'content': ...}] e devolve LLMResult."""

    def count_failure(self) -> None:
        """Hook opcional para circuit breaker no factory."""

    def reset_failures(self) -> None:
        """Hook opcional para circuit breaker no factory."""
