from __future__ import annotations

from django.conf import settings

from ai.providers.anthropic_provider import AnthropicProvider
from ai.providers.base import BaseChatProvider, LLMResult, ProviderError
from ai.providers.mock_provider import MockProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.providers.opencode_provider import OpenCodeProvider

PROVIDER_REGISTRY: dict[str, type[BaseChatProvider]] = {
    'openai': OpenAIProvider,
    'opencode': OpenCodeProvider,
    'anthropic': AnthropicProvider,
    'mock': MockProvider,
}

FALLBACK_PROVIDER = 'mock'
CIRCUIT_BREAKER_THRESHOLD = 3


class LLMFactory:
    """Resolve provedor/modelo (sessão → tenant → global → settings) e aplica fallback."""

    _failure_counts: dict[str, int] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[BaseChatProvider]) -> None:
        PROVIDER_REGISTRY[name] = provider_cls

    @classmethod
    def available(cls) -> list[str]:
        return sorted(PROVIDER_REGISTRY)

    @classmethod
    def create(cls, provider: str | None = None, model: str | None = None, **kwargs) -> BaseChatProvider:
        name = (provider or getattr(settings, 'AI_DEFAULT_PROVIDER', 'mock') or 'mock').lower()
        model_name = model or getattr(settings, 'AI_DEFAULT_MODEL', '') or None

        if cls._is_circuit_open(name):
            name = FALLBACK_PROVIDER

        provider_cls = PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            if name != FALLBACK_PROVIDER:
                return cls.create(FALLBACK_PROVIDER, model=None, **kwargs)
            raise ProviderError(f'Provedor desconhecido: {name}')

        try:
            return provider_cls(model=model_name, **kwargs)
        except ProviderError:
            if name != FALLBACK_PROVIDER:
                return cls.create(FALLBACK_PROVIDER, model=None, **kwargs)
            raise

    @classmethod
    def complete(cls, messages: list[dict], provider: str | None = None, model: str | None = None, **kwargs) -> LLMResult:
        name = (provider or getattr(settings, 'AI_DEFAULT_PROVIDER', 'mock') or 'mock').lower()
        circuit_open = cls._is_circuit_open(name)
        instance = cls.create(provider=name, model=model, **kwargs)
        try:
            result = instance.complete(messages, **kwargs)
        except ProviderError:
            cls.record_failure(name)
            if instance.name != FALLBACK_PROVIDER and cls._is_circuit_open(name):
                fallback = cls.create(provider=FALLBACK_PROVIDER)
                result = fallback.complete(messages)
                result.fallback = True
            else:
                raise
        else:
            if circuit_open and instance.name == FALLBACK_PROVIDER and name != FALLBACK_PROVIDER:
                result.fallback = True
        if not result.fallback:
            cls.reset_failures(name)
        return result

    @classmethod
    def record_failure(cls, name: str) -> None:
        cls._failure_counts[name] = cls._failure_counts.get(name, 0) + 1

    @classmethod
    def reset_failures(cls, name: str) -> None:
        cls._failure_counts.pop(name, None)

    @classmethod
    def _is_circuit_open(cls, name: str) -> bool:
        if name == FALLBACK_PROVIDER:
            return False
        return cls._failure_counts.get(name, 0) >= CIRCUIT_BREAKER_THRESHOLD

    @classmethod
    def reset_circuit(cls) -> None:
        cls._failure_counts.clear()
