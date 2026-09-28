from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai.config import resolve_ai_config
from ai.models import AIConfig, ChatSession, ChatMessage, SourceDocument, SemanticCache, TokenUsage
from ai.providers import (
    AnthropicProvider,
    LLMFactory,
    MockProvider,
    OpenAIProvider,
    ProviderError,
)
from tenants.models import Tenant

User = get_user_model()


class FactoryTests(TestCase):
    def test_available_providers(self):
        available = LLMFactory.available()
        self.assertIn('mock', available)
        self.assertIn('openai', available)
        self.assertIn('anthropic', available)

    @override_settings(AI_DEFAULT_PROVIDER='mock', AI_DEFAULT_MODEL='mock-model')
    def test_create_defaults_from_settings(self):
        provider = LLMFactory.create()
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.model, 'mock-model')

    def test_create_openai(self):
        provider = LLMFactory.create(provider='openai', model='gpt-4o')
        self.assertIsInstance(provider, OpenAIProvider)
        self.assertEqual(provider.model, 'gpt-4o')

    def test_create_anthropic(self):
        provider = LLMFactory.create(provider='anthropic', model='claude-x')
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider.model, 'claude-x')

    def test_create_unknown_falls_back_to_mock(self):
        provider = LLMFactory.create(provider='nao-existe')
        self.assertIsInstance(provider, MockProvider)

    def test_register_custom_provider(self):
        class CustomProvider(MockProvider):
            name = 'custom'

        try:
            LLMFactory.register('custom', CustomProvider)
            provider = LLMFactory.create(provider='custom')
            self.assertIsInstance(provider, CustomProvider)
        finally:
            from ai.providers.factory import PROVIDER_REGISTRY

            PROVIDER_REGISTRY.pop('custom', None)

    def test_complete_returns_llm_result(self):
        result = LLMFactory.complete(
            [{'role': 'user', 'content': 'olá'}],
            provider='mock',
        )
        self.assertEqual(result.provider, 'mock')
        self.assertIn('olá', result.content)
        self.assertFalse(result.fallback)


class FallbackTests(TestCase):
    def setUp(self):
        LLMFactory.reset_circuit()

    def tearDown(self):
        LLMFactory.reset_circuit()

    def test_record_failure_opens_circuit(self):
        for _ in range(3):
            LLMFactory.record_failure('openai')
        self.assertTrue(LLMFactory._is_circuit_open('openai'))
        provider = LLMFactory.create(provider='openai')
        self.assertIsInstance(provider, MockProvider)

    def test_reset_failures_closes_circuit(self):
        LLMFactory.record_failure('openai')
        LLMFactory.record_failure('openai')
        LLMFactory.reset_failures('openai')
        self.assertFalse(LLMFactory._is_circuit_open('openai'))

    def test_complete_provider_error_raises_without_circuit(self):
        from ai.providers.base import BaseChatProvider

        class BoomProvider(BaseChatProvider):
            name = 'boom'

            def complete(self, messages, **kwargs):
                raise ProviderError('boom')

        LLMFactory.register('boom', BoomProvider)
        try:
            with self.assertRaises(ProviderError):
                LLMFactory.complete([{'role': 'user', 'content': 'x'}], provider='boom')
        finally:
            from ai.providers.factory import PROVIDER_REGISTRY

            PROVIDER_REGISTRY.pop('boom', None)
            LLMFactory.reset_circuit()

    def test_complete_with_open_circuit_uses_mock_fallback(self):
        for _ in range(3):
            LLMFactory.record_failure('anthropic')
        result = LLMFactory.complete(
            [{'role': 'user', 'content': 'teste'}],
            provider='anthropic',
        )
        self.assertEqual(result.provider, 'mock')
        self.assertTrue(result.fallback)


class ResolutionOrderTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name='Alpha', document='11111111000111')
        self.tenant_b = Tenant.objects.create(name='Beta', document='22222222000122')
        self.user = User.objects.create_user(
            email='tech@alpha.com',
            password='x',
            tenant=self.tenant_a,
            role='TECHNICIAN',
        )

    def test_settings_when_nothing_configured(self):
        resolved = resolve_ai_config(user=self.user)
        self.assertEqual(resolved['source'], 'settings')
        self.assertEqual(resolved['provider'], 'mock')

    def test_global_config_when_no_tenant_config(self):
        AIConfig.objects.create(
            tenant=None,
            provider='openai',
            model_name='gpt-4o-mini',
            is_active=True,
        )
        resolved = resolve_ai_config(user=self.user, tenant=self.tenant_b)
        self.assertEqual(resolved['source'], 'global')
        self.assertEqual(resolved['provider'], 'openai')

    def test_tenant_config_overrides_global(self):
        AIConfig.objects.create(
            tenant=None,
            provider='openai',
            model_name='gpt-4o-mini',
            is_active=True,
        )
        AIConfig.objects.create(
            tenant=self.tenant_a,
            provider='anthropic',
            model_name='claude-3-5-haiku',
            is_active=True,
        )
        resolved = resolve_ai_config(user=self.user, tenant=self.tenant_a)
        self.assertEqual(resolved['source'], 'tenant')
        self.assertEqual(resolved['provider'], 'anthropic')
        self.assertEqual(resolved['model_name'], 'claude-3-5-haiku')

    def test_session_override_wins(self):
        AIConfig.objects.create(
            tenant=self.tenant_a,
            provider='anthropic',
            model_name='claude-3-5-haiku',
            is_active=True,
        )
        session = ChatSession.objects.create(
            user=self.user,
            tenant=self.tenant_a,
            model_provider='mock',
            model_name='session-model',
        )
        resolved = resolve_ai_config(session=session, user=self.user, tenant=self.tenant_a)
        self.assertEqual(resolved['source'], 'session')
        self.assertEqual(resolved['provider'], 'mock')
        self.assertEqual(resolved['model_name'], 'session-model')

    def test_inactive_tenant_config_skipped(self):
        AIConfig.objects.create(
            tenant=self.tenant_a,
            provider='anthropic',
            model_name='claude',
            is_active=False,
        )
        AIConfig.objects.create(
            tenant=None,
            provider='openai',
            model_name='gpt-4o',
            is_active=True,
        )
        resolved = resolve_ai_config(user=self.user, tenant=self.tenant_a)
        self.assertEqual(resolved['source'], 'global')
        self.assertEqual(resolved['provider'], 'openai')

    def test_tenant_isolation_ai_config(self):
        AIConfig.objects.create(
            tenant=self.tenant_b,
            provider='anthropic',
            model_name='claude-b',
            is_active=True,
        )
        resolved = resolve_ai_config(user=self.user, tenant=self.tenant_a)
        self.assertEqual(resolved['source'], 'settings')
        self.assertEqual(resolved['provider'], 'mock')

    def test_session_without_override_uses_tenant_config(self):
        AIConfig.objects.create(
            tenant=self.tenant_a,
            provider='openai',
            model_name='gpt-4o',
            is_active=True,
        )
        session = ChatSession.objects.create(
            user=self.user,
            tenant=self.tenant_a,
            model_provider='',
            model_name='',
        )
        resolved = resolve_ai_config(session=session)
        self.assertEqual(resolved['source'], 'tenant')
        self.assertEqual(resolved['provider'], 'openai')


class AIModelTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Gamma', document='33333333000133')
        self.user = User.objects.create_user(
            email='g@g.com',
            password='x',
            tenant=self.tenant,
            role='STAFF',
        )

    def test_chat_session_and_message(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        message = ChatMessage.objects.create(
            session=session,
            tenant=self.tenant,
            role='user',
            content='olá',
        )
        self.assertEqual(session.messages.count(), 1)
        self.assertEqual(message.role, 'user')

    def test_token_usage(self):
        session = ChatSession.objects.create(user=self.user, tenant=self.tenant)
        usage = TokenUsage.objects.create(
            tenant=self.tenant,
            session=session,
            user=self.user,
            provider='mock',
            model_name='mock-model',
            prompt_tokens=10,
            completion_tokens=5,
        )
        self.assertEqual(usage.prompt_tokens, 10)

    def test_source_document_hash_unique_per_tenant(self):
        SourceDocument.objects.create(
            tenant=self.tenant,
            title='Manual',
            content='texto',
            content_hash='a' * 64,
        )
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SourceDocument.objects.create(
                    tenant=self.tenant,
                    title='Manual 2',
                    content='texto',
                    content_hash='a' * 64,
                )

    def test_semantic_cache(self):
        from django.utils import timezone

        cache = SemanticCache.objects.create(
            tenant=self.tenant,
            question_normalized='o que e ekg',
            answer='E(kg) é a divisão.',
            model_name='mock-model',
            expires_at=timezone.now(),
        )
        self.assertEqual(cache.hit_count, 0)

    def test_ai_config_unique_per_tenant(self):
        AIConfig.objects.create(tenant=self.tenant, provider='mock')
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AIConfig.objects.create(tenant=self.tenant, provider='openai')
