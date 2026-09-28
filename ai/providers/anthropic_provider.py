from __future__ import annotations

import os
import time

from django.conf import settings

from ai.providers.base import BaseChatProvider, LLMResult, ProviderError


class AnthropicProvider(BaseChatProvider):
    name = 'anthropic'
    default_model = 'claude-3-5-haiku-latest'

    def __init__(self, model: str | None = None, **kwargs):
        super().__init__(model=model, **kwargs)
        self._client = None
        self._failures = 0

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None) or os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ProviderError('ANTHROPIC_API_KEY não configurada.')
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError('Pacote anthropic não instalado.') from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def complete(self, messages: list[dict], **kwargs) -> LLMResult:
        client = self._get_client()
        system = None
        chat_messages = []
        for message in messages:
            if message.get('role') == 'system':
                system = (system + '\n' if system else '') + str(message.get('content', ''))
            else:
                chat_messages.append(message)
        started = time.monotonic()
        try:
            response = client.messages.create(
                model=self.model or self.default_model,
                system=system,
                messages=chat_messages,
                max_tokens=kwargs.pop('max_tokens', 1024),
                **kwargs,
            )
        except Exception as exc:
            self._failures += 1
            raise ProviderError(str(exc)) from exc
        self._failures = 0
        content = ''.join(
            block.text for block in response.content if getattr(block, 'type', None) == 'text'
        )
        usage = getattr(response, 'usage', None)
        latency = int((time.monotonic() - started) * 1000)
        return LLMResult(
            content=content,
            provider=self.name,
            model_name=response.model,
            prompt_tokens=getattr(usage, 'input_tokens', 0) or 0,
            completion_tokens=getattr(usage, 'output_tokens', 0) or 0,
            latency_ms=latency,
        )

    @property
    def consecutive_failures(self) -> int:
        return self._failures
