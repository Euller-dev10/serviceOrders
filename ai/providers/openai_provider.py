from __future__ import annotations

import os
import time

from django.conf import settings

from ai.providers.base import BaseChatProvider, LLMResult, ProviderError


class OpenAIProvider(BaseChatProvider):
    name = 'openai'
    default_model = 'gpt-4o-mini'

    def __init__(self, model: str | None = None, **kwargs):
        super().__init__(model=model, **kwargs)
        self._client = None
        self._failures = 0

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ProviderError('OPENAI_API_KEY não configurada.')
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError('Pacote openai não instalado.') from exc
        self._client = OpenAI(api_key=api_key)
        return self._client

    def complete(self, messages: list[dict], **kwargs) -> LLMResult:
        client = self._get_client()
        started = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=self.model or self.default_model,
                messages=messages,
                **kwargs,
            )
        except Exception as exc:
            self._failures += 1
            raise ProviderError(str(exc)) from exc
        self._failures = 0
        choice = response.choices[0].message
        usage = getattr(response, 'usage', None)
        latency = int((time.monotonic() - started) * 1000)
        return LLMResult(
            content=choice.content or '',
            provider=self.name,
            model_name=response.model,
            prompt_tokens=getattr(usage, 'prompt_tokens', 0) or 0,
            completion_tokens=getattr(usage, 'completion_tokens', 0) or 0,
            cached_tokens=getattr(getattr(usage, 'prompt_tokens_details', None), 'cached_tokens', 0) or 0,
            latency_ms=latency,
        )

    @property
    def consecutive_failures(self) -> int:
        return self._failures
