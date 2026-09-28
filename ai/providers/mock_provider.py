from __future__ import annotations

import time

from ai.providers.base import BaseChatProvider, LLMResult


class MockProvider(BaseChatProvider):
    name = 'mock'
    default_model = 'mock-model'

    def __init__(self, model: str | None = None, response: str | None = None, **kwargs):
        super().__init__(model=model, **kwargs)
        self._response = response

    def complete(self, messages: list[dict], **kwargs) -> LLMResult:
        started = time.monotonic()
        if self._response is not None:
            content = self._response
        else:
            last_user = next(
                (m.get('content', '') for m in reversed(messages) if m.get('role') == 'user'),
                '',
            )
            content = f'[mock] {last_user}'
        latency = int((time.monotonic() - started) * 1000)
        return LLMResult(
            content=content,
            provider=self.name,
            model_name=self.model or self.default_model,
            prompt_tokens=sum(len(str(m.get('content', ''))) for m in messages) // 4,
            completion_tokens=len(content) // 4,
            latency_ms=latency,
        )
