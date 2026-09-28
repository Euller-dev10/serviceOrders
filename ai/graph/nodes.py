"""Nós do grafo: router, tools, retrieve, condense_history, synthesize, persist."""

from __future__ import annotations

import json
import re

from django.conf import settings

from ai.config import resolve_ai_config
from ai.graph.state import AgentState
from ai.providers import LLMFactory, ProviderError
from ai.services import (
    build_system_prompt,
    check_rate_limit,
    condense_history,
    embed_text,
    get_exact_cache,
    get_semantic_cache,
    record_token_usage,
    set_exact_cache,
    set_semantic_cache,
)
from ai.tools import run_tool
from ai.tools.service_order_tools import ToolError
from ai.models import SourceDocument as AISourceDocument

TOOL_ROUTE_KEYWORDS = re.compile(
    r'\b(list(ar|e)|buscar|busc(ar|a)|qual(is)?|quanti?c|quantos|mostrar|detalh|histórico|'
    r'historico|agrup|soma|contar|os |ordem|cliente|balança|balanca|selo|laudo|relat[óo]rio)\b',
    re.I,
)
RAG_KEYWORDS = re.compile(
    r'\b(como|manual|norma|procedimento|pol[íi]tica|regra|tutorial|documentação|documentacao)\b',
    re.I,
)

FRIENDLY_TOOL_ERROR = (
    'Não consegui executar a ferramenta com os dados informados. '
    'Verifique o número/documento e tente de novo.'
)


def _last_user_question(state: AgentState) -> str:
    if state.get('question'):
        return state['question']
    for message in reversed(state.get('messages') or []):
        if message.get('role') == 'user':
            return str(message.get('content', ''))
    return ''


def condense_history_node(state: AgentState) -> dict:
    messages = list(state.get('messages') or [])
    condensed, summary = condense_history(messages)
    system_prompt = build_system_prompt(
        user_role=state.get('user_role', 'usuário'),
        user_name=state.get('user_name', ''),
        tenant_name=state.get('tenant_name', ''),
    )
    question = _last_user_question(state)
    return {
        'condensed_messages': condensed,
        'summary': summary,
        'system_prompt': system_prompt,
        'question': question,
    }


def router_node(state: AgentState) -> dict:
    question = state.get('question') or ''
    if RAG_KEYWORDS.search(question) and not TOOL_ROUTE_KEYWORDS.search(question):
        route = 'retrieve'
    elif TOOL_ROUTE_KEYWORDS.search(question):
        route = 'tools'
    else:
        route = 'direct'
    return {'route': route}


def tools_node(state: AgentState) -> dict:
    tenant_id = state.get('tenant_id') or 0
    if not tenant_id:
        return {
            'tool_results': [],
            'error': 'Contexto de empresa ausente.',
        }
    if not check_rate_limit(state.get('user_id') or 0):
        return {
            'tool_results': [],
            'error': 'Limite de consultas de IA atingido. Aguarde alguns minutos.',
        }

    question = state.get('question') or ''
    tool_results: list[dict] = []

    # Heurística simples para escolher tool (o grafo real pode usar LLM tool-calling)
    tool_name, args = _select_tool(question, state)
    try:
        result = run_tool(
            tool_name,
            args,
            tenant_id=tenant_id,
            user_id=state.get('user_id'),
            user_role=state.get('user_role_code'),
        )
        tool_results.append({'tool': tool_name, 'ok': True, 'result': result})
        error = None
    except ToolError as exc:
        tool_results.append({'tool': tool_name, 'ok': False, 'error': str(exc)})
        error = str(exc)
    except Exception:
        tool_results.append({'tool': tool_name, 'ok': False, 'error': FRIENDLY_TOOL_ERROR})
        error = FRIENDLY_TOOL_ERROR

    out: dict = {'tool_results': tool_results}
    if error:
        out['error'] = error
    return out


def _select_tool(question: str, state: AgentState) -> tuple[str, dict]:
    q = question.lower()
    number_match = re.search(r'\b(\d{1,6})\b', q)
    client_match = re.search(r'\b(?:empresa|cliente)\s+(.+?)(?=\s+qual\b|[,?.]|$)', q, re.I)
    client_name = client_match.group(1).strip() if client_match else None
    if 'laudo' in q or 'relatório' in q or 'relatorio' in q or 'rascunho' in q:
        if number_match:
            return 'draft_service_report', {'number': int(number_match.group(1))}
        return 'search_service_orders', {'limit': 5}
    if 'cliente' in q and ('buscar' in q or 'buscar' in q or 'qual' in q or 'detalh' in q):
        digits = re.sub(r'\D', '', question)
        if digits:
            return 'get_client', {'document': digits}
        return 'search_service_orders', {'limit': 5}
    if 'balança' in q or 'balanca' in q or 'histórico' in q or 'historico' in q:
        return 'list_scale_history', {'limit': 10}
    if 'quantos' in q or 'quantidade' in q or 'agrup' in q or 'contar' in q or 'soma' in q:
        return 'aggregate_service_orders', {'group_by': 'service_flag'}
    if 'os ' in q or 'ordem' in q or 'ordens' in q:
        if number_match and re.search(r'\b(os|ordem|#)\b', q):
            return 'get_service_order', {'number': int(number_match.group(1))}
        args = {'limit': 10}
        if client_name:
            args['client_name'] = client_name
        return 'search_service_orders', args
    return 'search_service_orders', {'limit': 10}


def retrieve_node(state: AgentState) -> dict:
    tenant_id = state.get('tenant_id') or 0
    question = state.get('question') or ''
    if not tenant_id or not question:
        return {'retrieved': []}

    qs = AISourceDocument.objects.filter(tenant_id=tenant_id, is_active=True)
    query_embedding = embed_text(question)

    # Ranking em Python (compatível SQLite/PG); em PG pode virar <=> com filtro tenant
    scored: list[tuple[float, AISourceDocument]] = []
    for doc in qs[:200]:
        text = doc.chunk or doc.content or ''
        score = 0.0
        if doc.embedding:
            from ai.services import cosine_similarity

            score = cosine_similarity(query_embedding, doc.embedding or [])
        # boost léxico simples
        q_tokens = set(question.lower().split())
        t_tokens = set(text.lower().split())
        if q_tokens and t_tokens:
            score += 0.1 * len(q_tokens & t_tokens) / len(q_tokens)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [
        {
            'title': doc.title,
            'doc_type': doc.doc_type,
            'snippet': (doc.chunk or doc.content or '')[:400],
            'score': round(score, 4),
        }
        for _, doc in scored[:3]
    ]
    return {'retrieved': top}


def synthesize_node(state: AgentState) -> dict:
    if state.get('error') and not state.get('tool_results') and not state.get('retrieved'):
        return {
            'answer': state['error'],
            'provider': 'none',
            'model_name': '',
            'cache_hit': False,
            'token_usage': {},
        }

    question = state.get('question') or ''
    tenant_id = state.get('tenant_id') or 0
    model_name = state.get('model_name') or getattr(settings, 'AI_DEFAULT_MODEL', 'mock-model')
    provider = state.get('provider') or getattr(settings, 'AI_DEFAULT_PROVIDER', 'mock')

    # Cache exato (apenas para intents estáticos — não para tools factuais)
    route = state.get('route') or 'direct'
    allow_cache = route in ('direct', 'retrieve')
    if allow_cache:
        cached = get_exact_cache(tenant_id, question, model_name)
        if cached:
            return {
                'answer': cached,
                'provider': provider,
                'model_name': model_name,
                'cache_hit': True,
                'token_usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'cached_tokens': 1},
            }
        embedding = embed_text(question)
        semantic = get_semantic_cache(
            tenant_id=tenant_id,
            question=question,
            model_name=model_name,
            embedding=embedding,
        )
        if semantic:
            return {
                'answer': semantic,
                'provider': provider,
                'model_name': model_name,
                'cache_hit': True,
                'token_usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'cached_tokens': 1},
            }

    context_parts: list[str] = []
    if state.get('summary'):
        context_parts.append(f'Conversa anterior (resumo): {state["summary"]}')
    if state.get('tool_results'):
        context_parts.append(
            'Resultados de ferramentas:\n'
            + json.dumps(state['tool_results'], ensure_ascii=False, default=str)[:4000]
        )
    if state.get('retrieved'):
        for i, chunk in enumerate(state['retrieved'], 1):
            context_parts.append(
                f'[[fonte: {chunk["title"]}]]\n{chunk["snippet"]}'
            )
    if state.get('error'):
        context_parts.append(f'Aviso: {state["error"]}')

    system_prompt = state.get('system_prompt') or build_system_prompt(
        user_role=state.get('user_role', 'usuário'),
        user_name=state.get('user_name', ''),
        tenant_name=state.get('tenant_name', ''),
    )
    if context_parts:
        system_prompt = system_prompt + '\n\nContexto:\n' + '\n\n'.join(context_parts)

    messages = [{'role': 'system', 'content': system_prompt}]
    for m in state.get('condensed_messages') or []:
        if m.get('role') != 'system':
            messages.append(m)
    if not any(m.get('role') == 'user' for m in messages):
        messages.append({'role': 'user', 'content': question})

    try:
        result = LLMFactory.complete(
            messages,
            provider=provider,
            model=state.get('model_name'),
            session_id=state.get('session_id'),
        )
    except ProviderError as exc:
        return {
            'answer': f'O assistente está indisponível no momento ({exc}). Tente novamente.',
            'provider': provider,
            'model_name': model_name,
            'cache_hit': False,
            'error': str(exc),
            'token_usage': {},
        }

    answer = result.content
    if allow_cache and answer and not result.fallback:
        set_exact_cache(tenant_id, question, model_name, answer)
        set_semantic_cache(
            tenant_id=tenant_id,
            question=question,
            model_name=model_name,
            answer=answer,
            embedding=embed_text(question),
        )

    return {
        'answer': answer,
        'provider': result.provider,
        'model_name': result.model_name or model_name,
        'cache_hit': False,
        'fallback': result.fallback,
        'token_usage': {
            'prompt_tokens': result.prompt_tokens,
            'completion_tokens': result.completion_tokens,
            'cached_tokens': result.cached_tokens,
        },
    }


def persist_node(state: AgentState) -> dict:
    from ai.models import ChatMessage, ChatSession

    session_id = state.get('session_id')
    tenant_id = state.get('tenant_id') or 0
    user_id = state.get('user_id') or 0
    if not session_id or not tenant_id or not user_id:
        return {}

    try:
        session = ChatSession.objects.get(pk=session_id, tenant_id=tenant_id)
    except ChatSession.DoesNotExist:
        return {}

    question = state.get('question') or ''
    answer = state.get('answer') or ''
    usage = state.get('token_usage') or {}

    if question:
        ChatMessage.objects.create(
            session=session,
            tenant_id=tenant_id,
            role='user',
            content=question,
        )
    if answer:
        ChatMessage.objects.create(
            session=session,
            tenant_id=tenant_id,
            role='assistant',
            content=answer,
            token_prompt=usage.get('prompt_tokens', 0),
            token_completion=usage.get('completion_tokens', 0),
        )

    if usage:
        record_token_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=state.get('provider') or 'unknown',
            model_name=state.get('model_name') or 'unknown',
            prompt_tokens=usage.get('prompt_tokens', 0),
            completion_tokens=usage.get('completion_tokens', 0),
            cached_tokens=usage.get('cached_tokens', 0),
            session=session,
        )

    if not session.title and question:
        session.title = question[:180]
        session.save(update_fields=['title'])

    return {}


def resolve_config_node(state: AgentState) -> dict:
    from accounts.models import User
    from tenants.models import Tenant

    tenant_id = state.get('tenant_id')
    user_id = state.get('user_id')
    tenant_name = state.get('tenant_name') or ''
    user_role = state.get('user_role') or 'usuário'
    user_name = state.get('user_name') or ''

    tenant = None
    user = None
    if tenant_id:
        tenant = Tenant.objects.filter(pk=tenant_id).first()
        if tenant:
            tenant_name = tenant.name
    if user_id:
        user = User.objects.filter(pk=user_id).first()
        if user:
            user_role = user.get_role_display() if hasattr(user, 'get_role_display') else user.role
            user_name = user.get_full_name() or user.email

    session = None
    if state.get('session_id'):
        from ai.models import ChatSession

        session = ChatSession.objects.filter(pk=state['session_id']).first()

    resolved = resolve_ai_config(session=session, tenant=tenant, user=user)
    return {
        'provider': resolved['provider'],
        'model_name': resolved.get('model_name') or '',
        'tenant_name': tenant_name,
        'user_role': user_role,
        'user_role_code': user.role if user else '',
        'user_name': user_name,
        'config': resolved,
    }
