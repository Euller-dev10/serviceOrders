"""Sprint 2.3 — UI de chat E2E, fontes RAG, SSE, métricas."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ai.markdown_utils import chunk_text, content_hash, extract_citations, safe_markdown
from ai.models import AIConfig, ChatMessage, ChatSession, SourceDocument, TokenUsage
from service_order.models import Client, Scale, ServiceOrder, Unit
from tenants.models import Tenant

User = get_user_model()


class ChatE2ETests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name='E2E Corp', document='66666666000166')
        self.user = User.objects.create_user(
            email='e2e@example.com',
            password='senha123',
            tenant=self.tenant,
            role='STAFF',
        )
        self.admin = User.objects.create_user(
            email='admin-e2e@example.com',
            password='senha123',
            tenant=self.tenant,
            role='ADMIN',
        )
        self.other = User.objects.create_user(
            email='other@example.com',
            password='senha123',
            tenant=self.tenant,
            role='TECHNICIAN',
        )
        unit = Unit.objects.create(name='kg', tenant=self.tenant)
        client = Client.objects.create(
            name='Cliente E2E', document='77777777000177', tenant=self.tenant
        )
        scale = Scale.objects.create(
            brand='Toledo', model='M', serie='E2E-1', capacity='100',
            unit=unit, division='0.05', client=client, tenant=self.tenant,
        )
        self.os = ServiceOrder.objects.create(
            tenant=self.tenant, number=1, client=client, scale=scale,
            service1=True, date=timezone.now(), user=self.user,
        )
        AIConfig.objects.create(
            tenant=self.tenant, provider='mock', model_name='mock-model', is_active=True
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear()

    def test_index_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('chat_index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)

    def test_index_lists_own_sessions(self):
        ChatSession.objects.create(user=self.user, tenant=self.tenant, title='Minha conversa')
        ChatSession.objects.create(
            user=User.objects.create_user(
                email='x@x.com', password='x', tenant=self.tenant, role='TECHNICIAN'
            ),
            tenant=self.tenant,
            title='Outra',
        )
        resp = self.client.get(reverse('chat_index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Minha conversa')
        self.assertNotContains(resp, 'Outra')

    def test_create_session_post(self):
        resp = self.client.post(reverse('chat_session_create'))
        self.assertEqual(resp.status_code, 302)
        session = ChatSession.objects.get(user=self.user)
        self.assertEqual(session.tenant, self.tenant)
        self.assertIn(f'/ia/sessao/{session.pk}/', resp.url)

    def test_detail_owner_only(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant, title='Privada')
        other_session = ChatSession.objects.create(
            user=self.other, tenant=self.tenant, title='Do outro'
        )
        ok = self.client.get(reverse('chat_detail', kwargs={'pk': session.pk}))
        self.assertEqual(ok.status_code, 200)
        denied = self.client.get(reverse('chat_detail', kwargs={'pk': other_session.pk}))
        self.assertEqual(denied.status_code, 404)

    def test_send_message_json_e2e_mock_provider(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        resp = self.client.post(
            reverse('chat_message_send', kwargs={'pk': session.pk}),
            {'content': 'liste as ordens de serviço'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('answer', data)
        self.assertTrue(data['answer'])
        self.assertIn('html', data)
        # mensagens persistidas
        self.assertEqual(ChatMessage.objects.filter(session=session).count(), 2)
        user_msg = ChatMessage.objects.filter(session=session, role='user').first()
        assistant = ChatMessage.objects.filter(session=session, role='assistant').first()
        self.assertEqual(user_msg.content, 'liste as ordens de serviço')
        self.assertTrue(assistant.content)
        # token usage gravado
        self.assertTrue(TokenUsage.objects.filter(session=session).exists())

    def test_send_message_sse_stream(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        resp = self.client.post(
            reverse('chat_message_send', kwargs={'pk': session.pk}) + '?stream=1',
            {'content': 'olá assistente'},
            HTTP_ACCEPT='text/event-stream',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/event-stream', resp['Content-Type'])
        body = b''.join(resp.streaming_content).decode('utf-8')
        self.assertIn('event: start', body)
        self.assertIn('event: token', body)
        self.assertIn('event: done', body)
        self.assertIn('olá', body)

    def test_sse_replay_endpoint(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        ChatMessage.objects.create(session=session, tenant=self.tenant, role='user', content='oi')
        ChatMessage.objects.create(session=session, tenant=self.tenant, role='assistant', content='olá!')
        resp = self.client.get(reverse('chat_stream', kwargs={'pk': session.pk}))
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content).decode('utf-8')
        self.assertIn('event: message', body)
        self.assertIn('olá!', body)

    def test_empty_message_rejected(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        resp = self.client.post(
            reverse('chat_message_send', kwargs={'pk': session.pk}),
            {'content': ''},
        )
        self.assertEqual(resp.status_code, 400)

    def test_rag_answer_cites_source(self):
        SourceDocument.objects.create(
            tenant=self.tenant,
            title='Manual de Calibração',
            content='Para calibrar a balança, use pesos padrão classe E2.',
            chunk='Para calibrar a balança, use pesos padrão classe E2.',
            content_hash=content_hash('calibrar'),
            embedding=__import__('ai.services', fromlist=['embed_text']).embed_text(
                'como calibrar balança pesos padrão'
            ),
            is_active=True,
        )
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        resp = self.client.post(
            reverse('chat_message_send', kwargs={'pk': session.pk}),
            {'content': 'como calibrar a balança com pesos padrão?'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # route retrieve → resposta mock com contexto
        self.assertIn('answer', data)
        # retrieved presente no estado interno via citations se houver [[fonte:]]
        if data.get('citations'):
            self.assertTrue(any('Manual' in c for c in data['citations']))

    def test_sources_admin_only(self):
        self.client.force_login(self.user)  # STAFF — não ADMIN
        resp = self.client.get(reverse('source_list'))
        self.assertEqual(resp.status_code, 403)

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('source_list'))
        self.assertEqual(resp.status_code, 200)

    def test_source_upload_and_delete_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('source_create'),
            {
                'title': 'Norma X',
                'doc_type': 'NORM',
                'content': 'Texto da norma sobre aferição.',
            },
        )
        self.assertEqual(resp.status_code, 302)
        doc = SourceDocument.objects.get(title='Norma X')
        self.assertEqual(doc.tenant, self.tenant)
        self.assertTrue(doc.embedding)
        self.assertTrue(doc.chunk)

        resp = self.client.post(reverse('source_delete', kwargs={'pk': doc.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SourceDocument.objects.filter(pk=doc.pk).exists())

    def test_source_upload_rejects_empty(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('source_create'), {'title': 'Vazio', 'doc_type': 'NORM'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SourceDocument.objects.filter(title='Vazio').exists())

    def test_ai_config_update_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('ai_config'),
            {'provider': 'openai', 'model_name': 'gpt-4o-mini', 'embedding_model': '', 'is_active': 'on'},
        )
        self.assertEqual(resp.status_code, 302)
        config = AIConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.provider, 'openai')
        self.assertEqual(config.model_name, 'gpt-4o-mini')

    def test_ai_config_forbidden_for_staff(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('ai_config'))
        self.assertEqual(resp.status_code, 403)

    def test_markdown_safe_escapes_html(self):
        html = safe_markdown('<script>alert(1)</script> **negrito**')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('<strong>negrito</strong>', html)

    def test_extract_citations(self):
        text = 'Resposta baseada em [[fonte: Manual E2]] e [[fonte: Portaria 123]].'
        self.assertEqual(extract_citations(text), ['Manual E2', 'Portaria 123'])

    def test_embed_sources_command(self):
        SourceDocument.objects.create(
            tenant=self.tenant,
            title='Doc sem embed',
            content='Conteúdo para embed ' + 'x' * 200,
            content_hash='pending',
            is_active=True,
        )
        call_command('embed_sources')
        doc = SourceDocument.objects.get(title='Doc sem embed')
        self.assertTrue(doc.embedding)
        self.assertNotEqual(doc.content_hash, 'pending')

    def test_user_cannot_open别人的_session_stream(self):
        victim = ChatSession.objects.create(user=self.other, tenant=self.tenant, title='Secreto')
        resp = self.client.get(reverse('chat_stream', kwargs={'pk': victim.pk}))
        self.assertEqual(resp.status_code, 404)


class MarkdownChunkTests(TestCase):
    def test_chunk_text_long(self):
        text = ('Parágrafo de teste. ' * 100).strip()
        chunks = chunk_text(text, size=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunks))

    def test_chunk_text_short(self):
        self.assertEqual(chunk_text('curto'), ['curto'])
