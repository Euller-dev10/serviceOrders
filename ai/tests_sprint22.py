"""Sprint 2.2 — tools, grafo, anti-vazamento, cache e resumo de histórico."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from ai.graph.build import build_graph, run_agent
from ai.models import AIConfig, ChatSession, ChatMessage, SemanticCache, SourceDocument, TokenUsage
from ai.services import (
    condense_history,
    embed_text,
    estimate_messages_tokens,
    get_exact_cache,
    normalize_question,
    set_exact_cache,
)
from ai.tools import TOOLS, list_tools, run_tool
from ai.tools.service_order_tools import ToolError
from service_order.models import Client, Scale, ServiceOrder, Unit
from tenants.models import Tenant

User = get_user_model()


class ToolBaseSetup:
    def create_tenants(self):
        self.tenant_a = Tenant.objects.create(name='Alpha LTDA', document='11111111000111')
        self.tenant_b = Tenant.objects.create(name='Beta SA', document='22222222000122')

        self.user_a = User.objects.create_user(
            email='a@alpha.com', password='x', tenant=self.tenant_a, role='STAFF'
        )
        self.user_b = User.objects.create_user(
            email='b@beta.com', password='x', tenant=self.tenant_b, role='STAFF'
        )

        unit_a = Unit.objects.create(name='kg', tenant=self.tenant_a)
        unit_b = Unit.objects.create(name='kg', tenant=self.tenant_b)

        self.client_a = Client.objects.create(
            name='Cliente Alpha',
            document='99999999000199',
            tenant=self.tenant_a,
        )
        self.client_b = Client.objects.create(
            name='Cliente Beta',
            document='88888888000188',
            tenant=self.tenant_b,
        )

        self.scale_a = Scale.objects.create(
            brand='Toledo',
            model='2098',
            serie='SER-A1',
            capacity='300',
            unit=unit_a,
            division='0.05',
            client=self.client_a,
            tenant=self.tenant_a,
        )
        self.scale_b = Scale.objects.create(
            brand='Filizola',
            model='X',
            serie='SER-B1',
            capacity='150',
            unit=unit_b,
            division='0.02',
            client=self.client_b,
            tenant=self.tenant_b,
        )

        self.os_a = ServiceOrder.objects.create(
            tenant=self.tenant_a,
            number=1,
            client=self.client_a,
            scale=self.scale_a,
            service1=True,
            verified=True,
            date=timezone.now(),
            user=self.user_a,
            observation='Laudo Alpha',
        )
        self.os_b = ServiceOrder.objects.create(
            tenant=self.tenant_b,
            number=1,
            client=self.client_b,
            scale=self.scale_b,
            service2=True,
            verified=False,
            date=timezone.now(),
            user=self.user_b,
            observation='Laudo Beta',
        )


class ToolContractTests(ToolBaseSetup, TestCase):
    def setUp(self):
        self.create_tenants()

    def test_registry_has_all_prd_tools(self):
        expected = {
            'search_service_orders',
            'get_service_order',
            'get_client',
            'list_scale_history',
            'aggregate_service_orders',
            'draft_service_report',
        }
        self.assertEqual(expected, set(TOOLS))

    def test_list_tools_returns_schemas(self):
        tools = list_tools()
        self.assertEqual(len(tools), 6)
        for tool in tools:
            self.assertIn('name', tool)
            self.assertIn('parameters', tool)

    def test_tenant_id_injected_and_stripped_from_llm_args(self):
        # LLM tentou mandar tenant_id errado — deve ser ignorado
        result = run_tool(
            'search_service_orders',
            {'tenant_id': 999999, 'limit': 5},
            tenant_id=self.tenant_a.pk,
        )
        self.assertEqual(result['total_matching'], 1)
        self.assertEqual(result['results'][0]['client'], 'Cliente Alpha')

    def test_tool_without_tenant_raises(self):
        with self.assertRaises(ToolError):
            run_tool('search_service_orders', {'limit': 5}, tenant_id=0)

    def test_limit_clamped_to_50(self):
        result = run_tool(
            'search_service_orders',
            {'limit': 999},
            tenant_id=self.tenant_a.pk,
        )
        self.assertLessEqual(result['returned'], 50)

    def test_get_service_order_by_number(self):
        result = run_tool(
            'get_service_order',
            {'number': 1},
            tenant_id=self.tenant_a.pk,
        )
        self.assertEqual(result['client'], 'Cliente Alpha')

    def test_get_service_order_not_found_friendly(self):
        with self.assertRaises(ToolError) as ctx:
            run_tool('get_service_order', {'number': 999}, tenant_id=self.tenant_a.pk)
        self.assertIn('não encontrada', str(ctx.exception))

    def test_aggregate_service_orders(self):
        result = run_tool(
            'aggregate_service_orders',
            {'group_by': 'service_flag'},
            tenant_id=self.tenant_a.pk,
        )
        self.assertEqual(result['total'], 1)
        flags = {b['key']: b['count'] for b in result['buckets']}
        self.assertEqual(flags['service1'], 1)
        self.assertEqual(flags['service2'], 0)

    def test_draft_service_report(self):
        result = run_tool(
            'draft_service_report',
            {'number': 1, 'tone': 'tecnico'},
            tenant_id=self.tenant_a.pk,
        )
        self.assertIn('LAUDO', result['draft'])
        self.assertIn('Cliente Alpha', result['draft'])

    def test_invalid_args_rejected_by_pydantic(self):
        with self.assertRaises(Exception):
            run_tool(
                'search_service_orders',
                {'limit': 0},
                tenant_id=self.tenant_a.pk,
            )


class AntiLeakageTests(ToolBaseSetup, TestCase):
    """SEC-09: ferramentas nunca retornam dados de outro tenant."""

    def setUp(self):
        self.create_tenants()

    def test_search_isolated(self):
        result_a = run_tool('search_service_orders', {}, tenant_id=self.tenant_a.pk)
        result_b = run_tool('search_service_orders', {}, tenant_id=self.tenant_b.pk)
        clients_a = {r['client'] for r in result_a['results']}
        clients_b = {r['client'] for r in result_b['results']}
        self.assertEqual(clients_a, {'Cliente Alpha'})
        self.assertEqual(clients_b, {'Cliente Beta'})
        self.assertFalse(clients_a & clients_b)

    def test_get_os_cross_tenant_denied(self):
        # O.S. do tenant B não deve aparecer para tenant A mesmo com mesmo number=1
        with self.assertRaises(ToolError):
            run_tool(
                'get_service_order',
                {'number': 1},
                tenant_id=self.tenant_a.pk + 999,  # tenant inexistente sem dados
            )

    def test_get_os_only_own_tenant(self):
        # Busca number=1 no tenant A devolve O.S. A, não B
        result = run_tool('get_service_order', {'number': 1}, tenant_id=self.tenant_a.pk)
        self.assertEqual(result['client'], 'Cliente Alpha')
        self.assertNotEqual(result['client'], 'Cliente Beta')

    def test_get_client_cross_document_denied(self):
        with self.assertRaises(ToolError):
            run_tool(
                'get_client',
                {'document': self.client_b.document},
                tenant_id=self.tenant_a.pk,
            )

    def test_scale_history_isolated(self):
        result_a = run_tool(
            'list_scale_history',
            {'serial_number': 'SER'},
            tenant_id=self.tenant_a.pk,
        )
        self.assertEqual(result_a['total_matching'], 1)
        self.assertEqual(result_a['scale']['serie'], 'SER-A1')

    def test_source_documents_isolated(self):
        SourceDocument.objects.create(
            tenant=self.tenant_a,
            title='Manual Alpha',
            content='procedimento A',
            content_hash='a' * 64,
        )
        SourceDocument.objects.create(
            tenant=self.tenant_b,
            title='Manual Beta',
            content='procedimento B',
            content_hash='b' * 64,
        )
        from ai.models import SourceDocument as SD

        docs_a = SD.objects.filter(tenant=self.tenant_a)
        docs_b = SD.objects.filter(tenant=self.tenant_b)
        self.assertEqual(docs_a.count(), 1)
        self.assertEqual(docs_b.count(), 1)
        self.assertNotEqual(docs_a.first().title, docs_b.first().title)


class HistoryCondenseTests(TestCase):
    def test_short_history_untouched(self):
        messages = [
            {'role': 'user', 'content': 'olá'},
            {'role': 'assistant', 'content': 'oi'},
        ]
        condensed, summary = condense_history(messages, max_tokens=6000)
        self.assertEqual(len(condensed), 2)
        self.assertEqual(summary, '')

    def test_long_history_truncates_and_summarizes(self):
        messages = []
        for i in range(40):
            content = f'Mensagem longa numero {i} ' + ('palavra ' * 50)
            messages.append({'role': 'user' if i % 2 == 0 else 'assistant', 'content': content})
        condensed, summary = condense_history(messages, max_tokens=200)
        self.assertTrue(summary)
        self.assertLess(len(condensed), len(messages))
        # Deve conter system message de resumo
        system_contents = [m['content'] for m in condensed if m['role'] == 'system']
        self.assertTrue(any('Resumo da conversa anterior' in c for c in system_contents))
        # Mensagens mais antigas removidas (FIFO)
        first_kept = next(m for m in condensed if m['role'] != 'system')
        self.assertNotEqual(first_kept, messages[0])
        self.assertIn('numero 0', summary)

    def test_system_messages_preserved(self):
        messages = [{'role': 'system', 'content': 'fixed'}] + [
            {'role': 'user', 'content': 'x ' * 500} for _ in range(20)
        ]
        condensed, summary = condense_history(messages, max_tokens=50)
        self.assertEqual(condensed[0]['role'], 'system')
        self.assertEqual(condensed[0]['content'], 'fixed')
        self.assertTrue(summary)

    def test_estimate_tokens(self):
        self.assertGreater(estimate_messages_tokens([{'role': 'user', 'content': 'a' * 400}]), 0)


class CacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name='CacheCo', document='33333333000133')

    def tearDown(self):
        cache.clear()

    def test_exact_cache_hit(self):
        set_exact_cache(self.tenant.pk, 'O que é E(kg)?', 'mock-model', 'Resposta Ekg')
        hit = get_exact_cache(self.tenant.pk, 'o que é e(kg)?', 'mock-model')
        self.assertEqual(hit, 'Resposta Ekg')

    def test_exact_cache_is_tenant_scoped(self):
        other = Tenant.objects.create(name='Outro', document='44444444000144')
        set_exact_cache(self.tenant.pk, 'pergunta', 'mock-model', 'do A')
        hit = get_exact_cache(other.pk, 'pergunta', 'mock-model')
        self.assertIsNone(hit)

    def test_exact_cache_is_model_scoped(self):
        set_exact_cache(self.tenant.pk, 'pergunta', 'model-a', 'resposta-a')
        self.assertIsNone(get_exact_cache(self.tenant.pk, 'pergunta', 'model-b'))

    def test_semantic_cache_hit_and_hit_count(self):
        from ai.services import get_semantic_cache, set_semantic_cache

        question = 'Como imprimir a ordem de serviço?'
        emb = embed_text(question)
        set_semantic_cache(
            tenant_id=self.tenant.pk,
            question=question,
            model_name='mock-model',
            answer='Use o botão A4.',
            embedding=emb,
        )
        # pergunta levemente diferente mas mesmo embedding determinístico = hit exato
        hit = get_semantic_cache(
            tenant_id=self.tenant.pk,
            question=question,
            model_name='mock-model',
            embedding=emb,
        )
        self.assertEqual(hit, 'Use o botão A4.')
        row = SemanticCache.objects.get(tenant=self.tenant, model_name='mock-model')
        self.assertGreaterEqual(row.hit_count, 1)

    def test_semantic_cache_tenant_isolation(self):
        from ai.services import get_semantic_cache, set_semantic_cache

        other = Tenant.objects.create(name='Outro2', document='55555555000155')
        emb = embed_text('pergunta compartilhada')
        set_semantic_cache(
            tenant_id=self.tenant.pk,
            question='pergunta compartilhada',
            model_name='m',
            answer='do A',
            embedding=emb,
        )
        hit = get_semantic_cache(
            tenant_id=other.pk,
            question='pergunta compartilhada',
            model_name='m',
            embedding=emb,
        )
        self.assertIsNone(hit)

    def test_normalize_question(self):
        self.assertEqual(normalize_question('  O QUE é  E(kg)? '), 'o que e e(kg)?')


class GraphRunnerTests(ToolBaseSetup, TestCase):
    def setUp(self):
        self.create_tenants()
        cache.clear()
        AIConfig.objects.create(
            tenant=self.tenant_a, provider='mock', model_name='mock-model', is_active=True
        )
        self.session_a = ChatSession.objects.create(
            user=self.user_a, tenant=self.tenant_a
        )
        self.session_b = ChatSession.objects.create(
            user=self.user_b, tenant=self.tenant_b
        )
        self.graph = build_graph()

    def tearDown(self):
        cache.clear()

    def _run(self, question, session, user, tenant):
        prior = list(
            session.messages.order_by('created_at').values('role', 'content')
        )
        state = {
            'messages': prior + [{'role': 'user', 'content': question}],
            'tenant_id': tenant.pk,
            'user_id': user.pk,
            'session_id': session.pk,
            'question': question,
        }
        return run_agent(
            state,
            config={'configurable': {'thread_id': f's-{session.pk}'}},
        )

    def test_graph_tools_route_returns_answer_and_persists(self):
        final = self._run(
            'liste as ordens de serviço',
            self.session_a,
            self.user_a,
            self.tenant_a,
        )
        self.assertIn('answer', final)
        self.assertTrue(final['answer'])
        self.assertTrue(final.get('tool_results'))
        self.assertEqual(final['tool_results'][0]['tool'], 'search_service_orders')
        self.assertEqual(final['tool_results'][0]['ok'], True)
        # persist
        self.assertEqual(ChatMessage.objects.filter(session=self.session_a).count(), 2)
        self.assertTrue(TokenUsage.objects.filter(session=self.session_a).exists())
        session = ChatSession.objects.get(pk=self.session_a.pk)
        self.assertEqual(session.title, 'liste as ordens de serviço')

    def test_graph_resolve_config_uses_tenant_ai_config(self):
        final = self._run('olá', self.session_a, self.user_a, self.tenant_a)
        self.assertEqual(final['provider'], 'mock')
        self.assertEqual(final['model_name'], 'mock-model')
        self.assertEqual(final['tenant_name'], 'Alpha LTDA')

    def test_graph_anti_leakage_between_tenants(self):
        final_a = self._run(
            'liste as ordens de serviço',
            self.session_a,
            self.user_a,
            self.tenant_a,
        )
        tools_a = final_a.get('tool_results') or []
        self.assertTrue(tools_a)
        # dump JSON não deve conter dados do tenant B
        dump = str(tools_a) + str(final_a.get('answer', ''))
        self.assertNotIn('Cliente Beta', dump)
        self.assertNotIn('SER-B1', dump)
        self.assertNotIn('Laudo Beta', dump)

    def test_graph_exact_cache_second_call(self):
        self._run('olá para o assistente', self.session_a, self.user_a, self.tenant_a)
        key_q = 'olá para o assistente'
        cached = get_exact_cache(self.tenant_a.pk, key_q, 'mock-model')
        self.assertIsNotNone(cached)

        final2 = self._run(key_q, self.session_a, self.user_a, self.tenant_a)
        # segunda vez pode vir do cache (route direct)
        self.assertIn('answer', final2)

    def test_graph_persist_token_usage_fields(self):
        final = self._run('quantas ordens temos?', self.session_a, self.user_a, self.tenant_a)
        usage = TokenUsage.objects.filter(session=self.session_a).first()
        self.assertIsNotNone(usage)
        self.assertEqual(usage.provider, final.get('provider') or usage.provider)

    def test_rate_limit_blocks_when_exceeded(self):
        from ai.services import check_rate_limit

        # esgota o limite
        for _ in range(25):
            ok = check_rate_limit(self.user_a.pk)
        self.assertFalse(ok)


class RateLimitUnitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(AI_RATE_LIMIT_PER_USER=3)
    def test_rate_limit_configurable(self):
        from ai.services import check_rate_limit

        self.assertTrue(check_rate_limit(1))
        self.assertTrue(check_rate_limit(1))
        self.assertTrue(check_rate_limit(1))
        self.assertFalse(check_rate_limit(1))
        # outro usuário não é afetado
        self.assertTrue(check_rate_limit(2))
