from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import AuditLog
from service_order.models import Client, Scale, ServiceOrder, Unit
from tenants.models import Tenant

User = get_user_model()


class Sprint33Base(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name='LGPD Ltda', document='11111111000111')
        self.admin = User.objects.create_user(
            email='admin@lgpd.test', password='SenhaForte1', role='ADMIN',
            tenant=self.tenant,
        )
        self.tech = User.objects.create_user(
            email='tech@lgpd.test', password='SenhaForte1', role='TECHNICIAN',
            tenant=self.tenant,
        )
        self.client_record = Client.objects.create(
            tenant=self.tenant, name='Titular Teste', document='22222222000122',
            email='titular@example.com', contact='41999999999', city='Curitiba',
        )
        unit = Unit.objects.create(tenant=self.tenant, name='kg')
        self.scale = Scale.objects.create(
            tenant=self.tenant, brand='Aferix', model='A1', serie='LGPD-1',
            capacity='100', unit=unit, division='0.01', client=self.client_record,
        )


class AuditAndPrivacyTests(Sprint33Base):
    def test_export_lgpd_is_admin_only_and_audited(self):
        ServiceOrder.objects.create(
            tenant=self.tenant, client=self.client_record, scale=self.scale,
            user=self.tech, signature='data:image/png;base64,signature',
        )
        self.client.force_login(self.tech)
        response = self.client.get(
            reverse('client_data_export', args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('client_data_export', args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['client']['email'], 'titular@example.com')
        self.assertEqual(payload['service_orders'][0]['signature'], 'data:image/png;base64,signature')
        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.ACTION_EXPORT, object_type='Client',
        ).exists())

    def test_anonimizacao_limpa_pii_assinatura_e_audita(self):
        order = ServiceOrder.objects.create(
            tenant=self.tenant, client=self.client_record, scale=self.scale,
            user=self.tech, signature='data:image/png;base64,signature',
            observation='PII observação',
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('client_anonymize', args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.client_record.refresh_from_db()
        order.refresh_from_db()
        self.assertTrue(self.client_record.name.startswith('Cliente anonimizado'))
        self.assertTrue(self.client_record.document.startswith('ANON-'))
        self.assertEqual(self.client_record.email, '')
        self.assertEqual(order.signature, '')
        self.assertEqual(order.observation, '')
        self.assertTrue(AuditLog.objects.filter(
            action=AuditLog.ACTION_ANONYMIZE, object_type='Client',
        ).exists())

    def test_lgpd_nao_acessa_cliente_de_outro_tenant(self):
        other = Tenant.objects.create(name='Outro', document='33333333000133')
        other_user = User.objects.create_user(
            email='other@lgpd.test', password='SenhaForte1', role='ADMIN', tenant=other,
        )
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('client_data_export', args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.client.force_login(other_user)
        response = self.client.get(
            reverse('client_data_export', args=[self.client_record.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_audit_retention_command(self):
        old = AuditLog.objects.create(
            tenant=self.tenant, actor=self.admin, action=AuditLog.ACTION_EXPORT,
            object_type='Client', object_id='1',
        )
        AuditLog.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        self.call_command('purge_audit_logs', '--days', '5')
        self.assertFalse(AuditLog.objects.filter(pk=old.pk).exists())

    def call_command(self, *args):
        from django.core.management import call_command

        return call_command(*args)


class LoginRateLimitTests(TestCase):
    @override_settings(LOGIN_RATE_LIMIT_PER_WINDOW=2, LOGIN_RATE_WINDOW_SECONDS=300)
    def test_login_rate_limit_por_ip(self):
        cache.clear()
        for _ in range(2):
            response = self.client.post(
                reverse('login'), {'email': 'wrong@example.com', 'password': 'wrong'}
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse('login'), {'email': 'wrong@example.com', 'password': 'wrong'}
        )
        self.assertEqual(response.status_code, 429)


class SecurityHeaderTests(TestCase):
    @override_settings(ENABLE_CSP=True)
    def test_csp_gradual_e_headers(self):
        response = self.client.get(reverse('login'))
        self.assertIn('Content-Security-Policy', response)
        self.assertIn('nosniff', response.get('X-Content-Type-Options', ''))
