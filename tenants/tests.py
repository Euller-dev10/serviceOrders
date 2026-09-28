from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ai.models import ChatMessage, ChatSession
from core.emails import notify_plan_limit_hit
from service_order.models import Client, Scale, ServiceOrder, Unit
from tenants.models import Plan, Subscription, Tenant
from tenants.services import (
    RESOURCE_AI,
    RESOURCE_OSES,
    RESOURCE_SEATS,
    check_plan_limit,
    count_ai_credits,
    count_seats,
    count_service_orders,
    get_or_create_trial_subscription,
    seed_plans,
)

User = get_user_model()


class PlanLimitTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Empresa A', document='12345678000199')
        self.other_tenant = Tenant.objects.create(
            name='Empresa B', document='98765432000199'
        )
        self.admin = User.objects.create_user(
            email='admin@aferix.test', password='password-123',
            tenant=self.tenant, role='ADMIN',
        )
        self.plan = Plan.objects.create(
            code='test', name='Teste', price_monthly_cents=14900, max_technicians=2,
            max_service_orders_per_month=1, max_ai_credits_per_month=1,
        )
        now = timezone.now()
        self.subscription = Subscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            status=Subscription.STATUS_ACTIVE,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
        self.client_record = Client.objects.create(
            tenant=self.tenant, name='Cliente', document='11111111000111'
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name='kg')
        self.scale = Scale.objects.create(
            tenant=self.tenant, brand='Aferix', model='A1', serie='A-001',
            capacity='100', unit=self.unit, division='0.01', client=self.client_record,
        )

    def create_order(self, *, tenant=None, client=None, scale=None, date=None):
        tenant = tenant or self.tenant
        client = client or self.client_record
        scale = scale or self.scale
        return ServiceOrder.objects.create(
            tenant=tenant, client=client, scale=scale, date=date or timezone.now()
        )

    def test_seed_plans_is_idempotent_and_updates_baseline(self):
        first = seed_plans()
        second = seed_plans()

        self.assertEqual(len(first), 4)
        self.assertEqual(Plan.objects.filter(code__in=['trial', 'basic', 'pro', 'enterprise']).count(), 4)
        self.assertEqual([plan.pk for plan in first], [plan.pk for plan in second])
        self.assertEqual(Plan.objects.get(code='basic').price_monthly_cents, 14900)

    def test_missing_tenant_subscription_gets_trial(self):
        self.tenant.subscription.delete()

        subscription = get_or_create_trial_subscription(self.tenant)

        self.assertEqual(subscription.plan.code, 'trial')
        self.assertEqual(subscription.status, Subscription.STATUS_TRIALING)
        self.assertLessEqual(
            subscription.current_period_end - subscription.current_period_start,
            timedelta(days=14, seconds=1),
        )

    def test_counters_are_tenant_scoped_and_use_current_period(self):
        self.create_order()
        self.create_order(tenant=self.other_tenant)
        inactive_user = User.objects.create_user(
            email='inactive@aferix.test', password='password-123',
            tenant=self.tenant, is_active=False,
        )
        User.objects.create_user(
            email='technician@aferix.test', password='password-123', tenant=self.tenant
        )
        session = ChatSession.objects.create(
            tenant=self.tenant, user=self.admin, title='Teste'
        )
        ChatMessage.objects.create(
            tenant=self.tenant, session=session, role='user', content='Pergunta'
        )
        ChatMessage.objects.create(
            tenant=self.tenant, session=session, role='assistant', content='Resposta'
        )
        other_user = User.objects.create_user(
            email='outro@aferix.test', password='password-123', tenant=self.other_tenant
        )
        other_session = ChatSession.objects.create(
            tenant=self.other_tenant, user=other_user, title='Outra'
        )
        ChatMessage.objects.create(
            tenant=self.other_tenant, session=other_session, role='user', content='Pergunta'
        )

        self.assertEqual(count_service_orders(self.tenant, self.subscription), 1)
        self.assertEqual(count_seats(self.tenant), 2)
        self.assertEqual(count_ai_credits(self.tenant, self.subscription), 1)
        self.assertFalse(inactive_user.is_active)

    def test_limit_status_detects_full_resources(self):
        self.create_order()
        User.objects.create_user(
            email='second@aferix.test', password='password-123', tenant=self.tenant
        )
        session = ChatSession.objects.create(
            tenant=self.tenant, user=self.admin, title='Teste'
        )
        ChatMessage.objects.create(
            tenant=self.tenant, session=session, role='user', content='Pergunta'
        )

        for resource in (RESOURCE_OSES, RESOURCE_SEATS, RESOURCE_AI):
            status = check_plan_limit(self.tenant, resource, hard=True)
            self.assertTrue(status.over_limit, resource)
            self.assertFalse(status.allowed, resource)

    def test_no_subscription_is_created_as_trial_and_subscription_expiry_blocks(self):
        other = Tenant.objects.create(name='Sem plano', document='22222222000199')
        status = check_plan_limit(other, RESOURCE_OSES, hard=True)
        self.assertTrue(status.allowed)
        self.assertEqual(status.plan_code, 'trial')
        self.assertEqual(other.subscription.plan.code, 'trial')

        self.subscription.current_period_end = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=['current_period_end'])
        expired = check_plan_limit(self.tenant, RESOURCE_OSES, hard=True)
        self.assertFalse(expired.allowed)
        self.assertTrue(expired.subscription_inactive)

    def test_order_create_view_blocks_at_plan_limit(self):
        self.create_order()
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('service_order', args=[self.client_record.pk, self.scale.pk])
        )

        self.assertRedirects(response, reverse('billing'))

    def test_billing_page_displays_current_plan_and_usage(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('billing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Plano atual')
        self.assertContains(response, 'R$ 149,00')

    def test_ai_plan_feature_disabled_denies_message_before_generation(self):
        self.plan.ai_enabled = False
        self.plan.save(update_fields=['ai_enabled'])
        session = ChatSession.objects.create(
            tenant=self.tenant, user=self.admin, title='Teste'
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('chat_message_send', args=[session.pk]),
            {'content': 'Como está o plano?'},
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn('não está habilitado', response.json()['error'])
        self.assertFalse(ChatMessage.objects.filter(session=session, role='user').exists())


class PlanLimitEmailTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.tenant = Tenant.objects.create(name='Notifica SA', document='66677788000166')
        self.admin = User.objects.create_user(
            email='admin@notifica.test', password='password-123',
            tenant=self.tenant, role='ADMIN',
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_notifica_limite_uma_vez_por_dia(self):
        first = notify_plan_limit_hit(self.tenant, RESOURCE_OSES)
        second = notify_plan_limit_hit(self.tenant, RESOURCE_AI)

        self.assertEqual(first, 1)
        self.assertEqual(second, 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Ordens de Serviço', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['admin@notifica.test'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_decorator_bloqueia_e_envia_email_uma_vez(self):
        plan = Plan.objects.create(
            code='zero-os', name='Zero OS', max_service_orders_per_month=0
        )
        now = timezone.now()
        Subscription.objects.create(
            tenant=self.tenant, plan=plan, status=Subscription.STATUS_ACTIVE,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
        client_record = Client.objects.create(
            tenant=self.tenant, name='Cliente N', document='12121212000121'
        )
        unit = Unit.objects.create(tenant=self.tenant, name='kg')
        scale = Scale.objects.create(
            tenant=self.tenant, brand='A', model='A1', serie='S-1',
            capacity='10', unit=unit, division='0.01', client=client_record,
        )
        self.client.force_login(self.admin)
        url = reverse('service_order', args=[client_record.pk, scale.pk])

        first = self.client.get(url)
        second = self.client.get(url)

        self.assertRedirects(first, reverse('billing'))
        self.assertRedirects(second, reverse('billing'))
        self.assertEqual(len(mail.outbox), 1)

    def test_sem_admin_nao_envia(self):
        self.admin.delete()
        self.assertEqual(notify_plan_limit_hit(self.tenant, RESOURCE_OSES), 0)
