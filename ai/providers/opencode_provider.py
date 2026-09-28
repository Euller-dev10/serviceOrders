from __future__ import annotations

import os
import time

from django.conf import settings

from ai.providers.openai_provider import OpenAIProvider
from ai.providers.base import LLMResult, ProviderError


class OpenCodeProvider(OpenAIProvider):
    """OpenCode Zen via sua API compatível com OpenAI Chat Completions."""

    name = 'opencode'
    default_model = 'gpt-5.6-luna'

    def complete(self, messages: list[dict], **kwargs) -> LLMResult:
        session_id = kwargs.pop('session_id', None)
        extra_headers = kwargs.pop('extra_headers', {})
        if session_id:
            extra_headers['x-opencode-session'] = f'aferix-session-{session_id}'
        if extra_headers:
            kwargs['extra_headers'] = extra_headers
        if (self.model or self.default_model).startswith('gpt-'):
            started = time.monotonic()
            try:
                response = self._get_client().responses.create(
                    model=self.model or self.default_model,
                    input=messages,
                    **kwargs,
                )
            except Exception as exc:
                raise ProviderError(str(exc)) from exc
            return LLMResult(
                content=response.output_text or '',
                provider=self.name,
                model_name=getattr(response, 'model', None) or self.model or self.default_model,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        return super().complete(messages, **kwargs)

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = getattr(settings, 'OPENCODE_API_KEY', None) or os.environ.get('OPENCODE_API_KEY')
        if not api_key:
            from ai.providers.base import ProviderError
            raise ProviderError('OPENCODE_API_KEY não configurada.')
        try:
            from openai import OpenAI
        except ImportError as exc:
            from ai.providers.base import ProviderError
            raise ProviderError('Pacote openai não instalado.') from exc
        base_url = (
            getattr(settings, 'OPENCODE_BASE_URL', None)
            or os.environ.get('OPENCODE_BASE_URL')
            or 'https://opencode.ai/zen/v1'
        )
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        return self._client
