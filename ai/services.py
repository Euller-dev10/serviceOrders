"""Gestão de contexto, cache, rate limit e persistência de uso de tokens."""

from __future__ import annotations

import hashlib
import time
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ai.models import ChatSession, SemanticCache, TokenUsage

SYSTEM_PROMPT_BASE = (
    'Você é o Assistente Aferix, especialista em ordens de serviço de balanças '
    'e metroligação. Responda sempre em pt-BR, de forma clara e objetiva. '
    'Use apenas dados do contexto/tenant informado; nunca invente números, '
    'clientes ou O.S. Se não houver dado, diga que não encontrou.'
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(str(m.get('content', ''))) for m in messages)


def build_system_prompt(*, user_role: str, user_name: str, tenant_name: str) -> str:
    return (
        f'{SYSTEM_PROMPT_BASE}\n'
        f'Perfil: {user_name} ({user_role}).\n'
        f'Empresa: {tenant_name}.'
    )


def condense_history(
    messages: list[dict],
    *,
    max_tokens: int | None = None,
    summarize=None,
) -> tuple[list[dict], str]:
    """Trunca histórico FIFO; mensagens antigas viram resumo (system message).

    Retorna (condensed_messages, summary).
    """
    if max_tokens is None:
        max_tokens = getattr(settings, 'AI_HISTORY_MAX_TOKENS', 6000)
    budget = int(max_tokens * 0.6)

    if not messages:
        return [], ''

    if estimate_messages_tokens(messages) <= budget:
        return list(messages), ''

    # Separa system fixo (se houver no início)
    system_msgs = [m for m in messages if m.get('role') == 'system']
    non_system = [m for m in messages if m.get('role') != 'system']

    # FIFO: remove as mais antigas até caber no orçamento
    kept: list[dict] = list(non_system)
    dropped: list[dict] = []
    while kept and estimate_messages_tokens(kept) > budget:
        dropped.insert(0, kept.pop(0))

    summary = ''
    if dropped:
        if summarize is not None:
            summary = summarize(dropped)
        else:
            summary = _default_summary(dropped)

    condensed: list[dict] = list(system_msgs)
    if summary:
        condensed.append({'role': 'system', 'content': f'Resumo da conversa anterior: {summary}'})
    condensed.extend(kept)
    return condensed, summary


def _default_summary(dropped: list[dict]) -> str:
    parts = []
    for m in dropped:
        role = m.get('role', '?')
        content = str(m.get('content', ''))[:120]
        parts.append(f'{role}: {content}')
    if len(parts) > 8:
        parts = parts[:4] + ['...'] + parts[-3:]
    return ' | '.join(parts)


def normalize_question(text: str) -> str:
    text = (text or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.split())[:500]


def exact_cache_key(tenant_id: int, normalized: str, model_name: str) -> str:
    raw = f'{tenant_id}|{normalized}|{model_name}'
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f'ai:exact:{digest}'


def get_exact_cache(tenant_id: int, question: str, model_name: str) -> str | None:
    key = exact_cache_key(tenant_id, normalize_question(question), model_name)
    return cache.get(key)


def set_exact_cache(
    tenant_id: int,
    question: str,
    model_name: str,
    answer: str,
    ttl: int = 3600,
) -> None:
    key = exact_cache_key(tenant_id, normalize_question(question), model_name)
    cache.set(key, answer, ttl)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def get_semantic_cache(
    *,
    tenant_id: int,
    question: str,
    model_name: str,
    embedding: list[float] | None,
    threshold: float = 0.95,
) -> str | None:
    """Cache semântico por tenant; similaridade cos ≥ threshold e mesmo modelo."""
    normalized = normalize_question(question)
    now = timezone.now()
    qs = SemanticCache.objects.filter(
        tenant_id=tenant_id,
        model_name=model_name,
        expires_at__gt=now,
    )
    # Match exato rápido primeiro
    exact = qs.filter(question_normalized=normalized).first()
    if exact is not None:
        SemanticCache.objects.filter(pk=exact.pk).update(hit_count=exact.hit_count + 1)
        return exact.answer

    if not embedding:
        return None

    best_answer = None
    best_score = 0.0
    for row in qs.iterator(chunk_size=100):
        score = cosine_similarity(embedding, row.question_embedding or [])
        if score >= threshold and score > best_score:
            best_score = score
            best_answer = row.answer

    if best_answer is not None:
        from django.db.models import F

        qs.filter(answer=best_answer).update(hit_count=F('hit_count') + 1)
    return best_answer


def set_semantic_cache(
    *,
    tenant_id: int,
    question: str,
    model_name: str,
    answer: str,
    embedding: list[float] | None,
    ttl_days: int = 7,
) -> None:
    normalized = normalize_question(question)
    if not normalized:
        return
    expires = timezone.now() + timezone.timedelta(days=ttl_days)
    SemanticCache.objects.update_or_create(
        tenant_id=tenant_id,
        question_normalized=normalized,
        model_name=model_name,
        defaults={
            'answer': answer,
            'question_embedding': embedding or [],
            'expires_at': expires,
        },
    )


def check_rate_limit(user_id: int) -> bool:
    """True se dentro do limite; False se estourou."""
    limit = getattr(settings, 'AI_RATE_LIMIT_PER_USER', 20)
    if limit <= 0:
        return True
    bucket = int(time.time() // 60)
    key = f'ai:rate:{user_id}:{bucket}'
    try:
        current = cache.get(key, 0)
    except Exception:
        return True
    if current >= limit:
        return False
    try:
        cache.set(key, current + 1, timeout=120)
    except Exception:
        pass
    return True


def record_token_usage(
    *,
    tenant_id: int,
    user_id: int,
    provider: str,
    model_name: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    session: ChatSession | None = None,
    cost_usd: float = 0.0,
) -> TokenUsage:
    return TokenUsage.objects.create(
        tenant_id=tenant_id,
        user_id=user_id,
        session=session,
        provider=provider,
        model_name=model_name or 'unknown',
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost_usd,
    )


class DeterministicEmbedder:
    """Embedding determinístico para testes/mock (sem chamada externa)."""

    def __init__(self, dim: int | None = None):
        self.dim = dim or getattr(settings, 'AI_EMBEDDING_DIM', 1536)

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        if not text:
            return vec
        tokens = normalize_question(text).split()
        for i, token in enumerate(tokens):
            h = int(hashlib.sha256(token.encode('utf-8')).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
            vec[(idx + i + 1) % self.dim] += 0.5 * sign
        # normaliza
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


def embed_text(text: str) -> list[float]:
    return DeterministicEmbedder().embed(text)
