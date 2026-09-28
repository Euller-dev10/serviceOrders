"""Views da UI de chat IA (Sprint 2.3) — §8.8 do PRD."""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, FormView, ListView, UpdateView

from ai.forms import AIConfigForm, SourceDocumentForm
from ai.config import resolve_ai_config
from ai.graph.build import run_agent
from ai.markdown_utils import extract_citations, safe_markdown
from ai.models import AIConfig, ChatSession, SourceDocument
from core.permissions import AdminRequiredMixin, TenantRequiredMixin
from tenants.services import RESOURCE_AI, check_plan_limit

logger = logging.getLogger(__name__)


def _tenant_id(user):
    if user.is_superuser:
        return None
    return getattr(user, 'tenant_id', None)


def _owned_session(request, pk):
    session = get_object_or_404(ChatSession, pk=pk)
    user = request.user
    if user.is_superuser:
        return session
    if session.user_id != user.pk or (
        getattr(user, 'tenant_id', None) and session.tenant_id != user.tenant_id
    ):
        raise Http404
    return session


@method_decorator(login_required(login_url='login'), name='dispatch')
class ChatIndexView(TenantRequiredMixin, ListView):
    model = ChatSession
    template_name = 'ai/chat_index.html'
    context_object_name = 'sessions'
    paginate_by = 50

    def get_queryset(self):
        qs = ChatSession.objects.filter(user=self.request.user, is_active=True)
        tenant_id = _tenant_id(self.request.user)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs.select_related('tenant')


@method_decorator(login_required(login_url='login'), name='dispatch')
class ChatSessionCreateView(TenantRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        tenant_id = _tenant_id(request.user)
        if tenant_id is None and not request.user.is_superuser:
            messages.error(request, 'Usuário sem tenant ativo.')
            return redirect('chat_index')
        session = ChatSession.objects.create(
            user=request.user,
            tenant_id=tenant_id,
            title='Nova conversa',
        )
        return redirect('chat_detail', pk=session.pk)


@method_decorator(login_required(login_url='login'), name='dispatch')
class ChatDetailView(TenantRequiredMixin, DetailView):
    model = ChatSession
    template_name = 'ai/chat_detail.html'
    context_object_name = 'session'

    def get_object(self, queryset=None):
        return _owned_session(self.request, self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        msgs = self.object.messages.order_by('created_at')
        rendered = []
        for m in msgs:
            rendered.append({
                'role': m.role,
                'html': safe_markdown(m.content),
                'citations': extract_citations(m.content),
                'created_at': m.created_at,
            })
        ctx['messages'] = rendered
        return ctx


def _sse_event(event: str, data: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n'


def _stream_answer_chunks(answer: str, chunk_size: int = 24):
    """Divide a resposta em pedaços para simular streaming SSE."""
    if not answer:
        yield _sse_event('token', {'text': ''})
        return
    for i in range(0, len(answer), chunk_size):
        yield _sse_event('token', {'text': answer[i:i + chunk_size]})


@method_decorator(login_required(login_url='login'), name='dispatch')
class ChatMessageSendView(TenantRequiredMixin, View):
    """POST mensagem → orquestra grafo → resposta (JSON ou SSE via ?stream=1)."""

    def post(self, request, pk, *args, **kwargs):
        session = _owned_session(request, pk)
        question = (request.POST.get('content') or request.POST.get('message') or '').strip()
        if not question:
            return JsonResponse({'error': 'Mensagem vazia.'}, status=400)

        tenant = session.tenant or getattr(request, 'tenant', None)
        access = check_plan_limit(tenant, RESOURCE_AI, hard=True)
        if not access.allowed:
            if access.subscription_inactive:
                error = 'A assinatura da empresa não está ativa. Consulte o faturamento para regularizar.'
            elif access.feature_disabled:
                error = 'O Assistente IA não está habilitado no plano atual.'
            else:
                error = 'Limite de créditos de IA atingido. Consulte o faturamento para atualizar o plano.'
            from core.emails import notify_plan_limit_hit

            notify_plan_limit_hit(tenant, RESOURCE_AI)
            return JsonResponse(
                {'error': error, 'billing_url': reverse('billing')},
                status=429,
            )

        tenant_id = session.tenant_id or _tenant_id(request.user)
        prior = list(session.messages.order_by('created_at').values('role', 'content'))
        state = {
            'messages': prior + [{'role': 'user', 'content': question}],
            'tenant_id': tenant_id or 0,
            'user_id': request.user.pk,
            'session_id': session.pk,
            'question': question,
            'user_role': getattr(request.user, 'role', 'user'),
            'user_name': request.user.get_full_name() or request.user.email,
            'tenant_name': session.tenant.name if session.tenant_id else '',
        }
        resolved_config = resolve_ai_config(session=session, tenant=tenant, user=request.user)
        state['provider'] = resolved_config['provider']
        state['model_name'] = resolved_config.get('model_name') or ''
        try:
            final = run_agent(
                state,
                config={'configurable': {'thread_id': f"session-{session.pk}-{resolved_config['provider']}-{resolved_config.get('model_name') or 'default'}"}},
            )
        except Exception:
            logger.exception('Falha ao executar o agente IA na sessão %s', session.pk)
            return JsonResponse(
                {'error': 'Não foi possível executar o Aferix IA. Verifique a configuração do provedor e tente novamente.'},
                status=500,
            )
        answer = final.get('answer') or ''
        citations = extract_citations(answer)

        if request.GET.get('stream') == '1' or request.headers.get('Accept') == 'text/event-stream':
            def event_stream():
                yield _sse_event('start', {'session_id': session.pk})
                yield from _stream_answer_chunks(answer)
                yield _sse_event('done', {
                    'answer': answer,
                    'html': safe_markdown(answer),
                    'citations': citations,
                    'route': final.get('route', ''),
                    'cache_hit': final.get('cache_hit', False),
                })

            return StreamingHttpResponse(
                event_stream(),
                content_type='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
            )

        return JsonResponse({
            'answer': answer,
            'html': safe_markdown(answer),
            'citations': citations,
            'route': final.get('route', ''),
            'cache_hit': final.get('cache_hit', False),
            'session_id': session.pk,
            'redirect': reverse('chat_detail', kwargs={'pk': session.pk}),
        })


@method_decorator(login_required(login_url='login'), name='dispatch')
class ChatStreamView(TenantRequiredMixin, View):
    """SSE de uma sessão (replay das mensagens + assinatura de novas via polling simples)."""

    def get(self, request, pk, *args, **kwargs):
        session = _owned_session(request, pk)

        def event_stream():
            yield _sse_event('open', {'session_id': session.pk})
            for m in session.messages.order_by('created_at'):
                yield _sse_event('message', {
                    'role': m.role,
                    'html': safe_markdown(m.content),
                    'citations': extract_citations(m.content),
                })
            yield _sse_event('end', {'session_id': session.pk})

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
            headers={'Cache-Control': 'no-cache'},
        )


@method_decorator(login_required(login_url='login'), name='dispatch')
class SourceDocumentListView(AdminRequiredMixin, TenantRequiredMixin, ListView):
    model = SourceDocument
    template_name = 'ai/source_list.html'
    context_object_name = 'documents'
    paginate_by = 50

    def get_queryset(self):
        qs = SourceDocument.objects.all().order_by('-updated_at')
        tenant_id = _tenant_id(self.request.user)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs


@method_decorator(login_required(login_url='login'), name='dispatch')
class SourceDocumentCreateView(AdminRequiredMixin, TenantRequiredMixin, FormView):
    form_class = SourceDocumentForm
    template_name = 'ai/source_form.html'
    success_url = '/ia/fontes/'

    def form_valid(self, form):
        tenant_id = _tenant_id(self.request.user)
        if tenant_id is None and not self.request.user.is_superuser:
            form.add_error(None, 'Usuário sem tenant ativo.')
            return self.form_invalid(form)
        instance = form.save(commit=False)
        if tenant_id:
            instance.tenant_id = tenant_id
        content = (instance.content or '').strip()
        if instance.file and not content:
            try:
                instance.file.open('rb')
                raw = instance.file.read()
                content = raw.decode('utf-8', errors='ignore')
                instance.file.seek(0)
            except Exception:
                content = ''
        instance.content = content
        from ai.markdown_utils import chunk_text, content_hash
        from ai.services import embed_text

        instance.content_hash = content_hash(content)
        chunks = chunk_text(content)
        instance.chunk = chunks[0] if chunks else content
        instance.embedding = embed_text(instance.chunk or content)
        instance.save()
        messages.success(self.request, 'Documento indexado com sucesso.')
        return super().form_valid(form)


@method_decorator(login_required(login_url='login'), name='dispatch')
class SourceDocumentDeleteView(AdminRequiredMixin, TenantRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        qs = SourceDocument.objects.all()
        tenant_id = _tenant_id(request.user)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        doc = get_object_or_404(qs, pk=pk)
        doc.delete()
        messages.success(request, 'Documento removido.')
        return redirect('source_list')


@method_decorator(login_required(login_url='login'), name='dispatch')
class AIConfigUpdateView(AdminRequiredMixin, TenantRequiredMixin, UpdateView):
    model = AIConfig
    form_class = AIConfigForm
    template_name = 'ai/config_form.html'

    def get_object(self, queryset=None):
        tenant_id = _tenant_id(self.request.user)
        config = AIConfig.objects.filter(tenant_id=tenant_id).first() if tenant_id else None
        if config is None:
            config = AIConfig(tenant_id=tenant_id, provider='mock', is_active=True)
        return config

    def form_valid(self, form):
        tenant_id = _tenant_id(self.request.user)
        if tenant_id is None:
            form.add_error(None, 'Superuser sem tenant — use o Django Admin.')
            return self.form_invalid(form)
        form.instance.tenant_id = tenant_id
        form.instance.is_active = True
        messages.success(self.request, 'Configuração de IA atualizada.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('ai_config')
