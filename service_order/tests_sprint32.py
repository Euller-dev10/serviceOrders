from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.test.utils import override_settings as os_override
from django.urls import reverse
from django.utils import timezone

from service_order.models import Client, Scale, ServiceOrder, TimeService, Unit
from tenants.models import Plan, Subscription, Tenant

User = get_user_model()


class Sprint32BaseSetup(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.tenant = Tenant.objects.create(name='Delta Ltda', document='11122233000144')
        self.other_tenant = Tenant.objects.create(
            name='Epsilon SA', document='55566677000188'
        )
        self.staff = User.objects.create_user(
            email='staff@delta.test', password='SenhaForte', role='STAFF', tenant=self.tenant
        )
        self.tech = User.objects.create_user(
            email='tech@delta.test', password='SenhaForte', role='TECHNICIAN',
            tenant=self.tenant,
        )
        self.client_entity = Client.objects.create(
            tenant=self.tenant, name='Cliente Delta', document='12121212000121',
            city='Curitiba',
        )
        self.other_client = Client.objects.create(
            tenant=self.other_tenant, name='Cliente Epsilon', document='13434343000134',
            city='São Paulo',
        )
        self.unit = Unit.objects.create(tenant=self.tenant, name='kg')
        self.scale = Scale.objects.create(
            tenant=self.tenant, brand='Aferix', model='A1', serie='S-D-1',
            capacity='100', unit=self.unit, division='0.01', client=self.client_entity,
        )
        self.other_unit = Unit.objects.create(tenant=self.other_tenant, name='kg')
        self.other_scale = Scale.objects.create(
            tenant=self.other_tenant, brand='Toledo', model='T1', serie='S-E-1',
            capacity='200', unit=self.other_unit, division='0.02',
            client=self.other_client,
        )

    def make_plan(self, *, required_signature=False, max_os=None):
        plan = Plan.objects.create(
            code='plan-32', name='Plano 32', max_technicians=5,
            max_service_orders_per_month=max_os,
            required_signature=required_signature,
        )
        now = timezone.now()
        Subscription.objects.create(
            tenant=self.tenant, plan=plan, status=Subscription.STATUS_ACTIVE,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
        return plan

    def os_payload(self, signature=''):
        return {
            'signature': signature,
            'observation': 'Servico teste 32',
            'service1': 'on',
            'service_order_part-TOTAL_FORMS': '0',
            'service_order_part-INITIAL_FORMS': '0',
            'service_order_part-MIN_NUM_FORMS': '0',
            'service_order_part-MAX_NUM_FORMS': '1000',
            'time_service-TOTAL_FORMS': '0',
            'time_service-INITIAL_FORMS': '0',
            'time_service-MIN_NUM_FORMS': '0',
            'time_service-MAX_NUM_FORMS': '1000',
        }


class DashboardTests(Sprint32BaseSetup):
    def test_dashboard_requer_staff(self):
        url = reverse('dashboard')

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_indicadores_no_ciclo(self):
        os1 = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.tech, tenant=self.tenant,
        )
        ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.tech, tenant=self.tenant,
            status=ServiceOrder.STATUS_CANCELED,
        )
        TimeService.objects.create(service_order=os1, total_hours=time(8, 30))

        self.client.force_login(self.staff)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Indicadores')
        self.assertEqual(response.context['os_total'], 2)
        status_map = {
            row['code']: row['count'] for row in response.context['os_by_status']
        }
        self.assertEqual(status_map[ServiceOrder.STATUS_COMPLETED], 1)
        self.assertEqual(status_map[ServiceOrder.STATUS_CANCELED], 1)
        self.assertEqual(response.context['technicians'][0]['count'], 2)
        self.assertEqual(response.context['tempo_medio_horas'], 8.5)
        self.assertEqual(response.context['tempo_medio_display'], '8,5h')


class ServiceOrderExportTests(Sprint32BaseSetup):
    def test_csv_os_escopo_tenant(self):
        ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.tech, tenant=self.tenant
        )
        ServiceOrder.objects.create(
            client=self.other_client, scale=self.other_scale, user=self.staff,
            tenant=self.other_tenant,
        )

        self.client.force_login(self.staff)
        response = self.client.get(reverse('os_export'), {'tipo': 'os'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        csv_text = response.content.decode('utf-8-sig')
        self.assertIn('Cliente Delta', csv_text)
        self.assertIn('Concluída', csv_text)
        self.assertNotIn('Cliente Epsilon', csv_text)

    def test_csv_tecnico_ve_apenas_proprias(self):
        os_own = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.tech, tenant=self.tenant
        )
        ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.staff, tenant=self.tenant
        )

        self.client.force_login(self.tech)
        response = self.client.get(reverse('os_export'), {'tipo': 'os'})
        csv_text = response.content.decode('utf-8-sig')
        self.assertIn(str(os_own.id), csv_text)
        self.assertEqual(csv_text.count('Cliente Delta'), 1)

    def test_csv_tipos_e_invalido(self):
        os1 = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.staff, tenant=self.tenant,
        )
        TimeService.objects.create(
            service_order=os1, day=date.today(), total_hours=time(4, 0), car='1.5'
        )
        self.client.force_login(self.staff)

        tempos = self.client.get(reverse('os_export'), {'tipo': 'tempos'})
        self.assertEqual(tempos.status_code, 200)
        self.assertIn('Caminhão', tempos.content.decode('utf-8-sig'))

        pecas = self.client.get(reverse('os_export'), {'tipo': 'pecas'})
        self.assertEqual(pecas.status_code, 200)
        self.assertIn('Base de troca', pecas.content.decode('utf-8-sig'))

        invalido = self.client.get(reverse('os_export'), {'tipo': 'x'})
        self.assertEqual(invalido.status_code, 400)


class SignatureRequiredTests(Sprint32BaseSetup):
    def test_plano_com_assinatura_obrigatoria_bloqueia_sem_assinatura(self):
        self.make_plan(required_signature=True)
        self.client.force_login(self.tech)
        url = reverse('service_order', args=[self.client_entity.pk, self.scale.pk])

        response = self.client.post(url, self.os_payload(signature=''))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'exige assinatura')
        self.assertFalse(
            ServiceOrder.objects.filter(client=self.client_entity).exists()
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_plano_com_assinatura_obrigatoria_aceita_com_assinatura(self):
        self.make_plan(required_signature=True)
        self.client.force_login(self.tech)
        url = reverse('service_order', args=[self.client_entity.pk, self.scale.pk])

        response = self.client.post(
            url, self.os_payload(signature='data:image/png;base64,AAA')
        )
        self.assertEqual(response.status_code, 302)
        os_obj = ServiceOrder.objects.get(client=self.client_entity)
        self.assertTrue(os_obj.signature)

    def test_plano_sem_assinatura_obrigatoria_pode_salvar_sem_assinatura(self):
        self.make_plan(required_signature=False)
        self.client.force_login(self.tech)
        url = reverse('service_order', args=[self.client_entity.pk, self.scale.pk])

        response = self.client.post(url, self.os_payload(signature=''))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceOrder.objects.filter(client=self.client_entity).exists())


class OsSignedEmailTests(Sprint32BaseSetup):
    @os_override(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_enviado_quando_assinada(self):
        self.admin = User.objects.create_user(
            email='admin@delta.test', password='SenhaForte', role='ADMIN',
            tenant=self.tenant,
        )
        self.client.force_login(self.tech)
        url = reverse('service_order', args=[self.client_entity.pk, self.scale.pk])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                url, self.os_payload(signature='data:image/png;base64,Assinado')
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('assinada', mail.outbox[0].subject)
        self.assertIn('admin@delta.test', mail.outbox[0].to)

    @os_override(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sem_assinatura_nao_envia_email(self):
        self.client.force_login(self.tech)
        url = reverse('service_order', args=[self.client_entity.pk, self.scale.pk])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(url, self.os_payload(signature=''))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(callbacks), 0)
        self.assertEqual(len(mail.outbox), 0)
