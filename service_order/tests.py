from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from service_order.models import (
    Client,
    Part,
    Scale,
    ServiceOrder,
    Stamp,
    StampDelivery,
    TechnicalReport,
    TimeService,
    Unit,
)
from service_order.services import consume_stamp_for_os, damage_delivery, distribute_stamp, next_os_number
from tenants.models import Tenant
from django.db import IntegrityError, transaction

User = get_user_model()


def make_logo_image(name='logo.png'):
    buffer = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class BaseSetup:
    def create_base(self):
        self.tenant = Tenant.objects.create(
            name='Empresa Alpha', document='12345678000199'
        )
        self.user = User.objects.create_user(
            email='tecnico@example.com',
            password='senha123',
            tenant=self.tenant,
            role='STAFF',
        )
        self.technician = User.objects.create_user(
            email='tecnico2@example.com',
            password='senha123',
            tenant=self.tenant,
            role='TECHNICIAN',
        )
        self.admin = User.objects.create_user(
            email='admin2@example.com',
            password='senha123',
            tenant=self.tenant,
            role='ADMIN',
        )
        self.superuser = User.objects.create_superuser(
            email='admin@example.com', password='senha123'
        )
        self.unit_kg = Unit.objects.create(name='kg', tenant=self.tenant)
        self.client_entity = Client.objects.create(
            name='Cliente Alfa',
            document='12345678000100',
            state_registration='1234567',
            address='Rua A, 10',
            district='Centro',
            city='Curitiba',
            uf='PR',
            cep='80000-000',
            contact='41 99999-0000',
            email='cliente@exemplo.com',
            tenant=self.tenant,
        )
        self.scale = Scale.objects.create(
            brand='Toledo',
            model='2098',
            serie='SER-001',
            capacity='300',
            unit=self.unit_kg,
            division='0.05',
            tag='TAG-01',
            client=self.client_entity,
            portaria='123/2020',
            tenant=self.tenant,
        )


class AccessTests(BaseSetup, TestCase):
    """Verifica que todas as views protegidas exigem login."""

    def setUp(self):
        self.create_base()

    def test_protected_urls_redirect_anonymous(self):
        protected_urls = [
            reverse('home'),
            reverse('search_client'),
            reverse('new_client'),
            reverse('search_scale'),
            reverse('new_scale'),
            reverse('scale_detail', args=[self.scale.pk]),
            reverse('scale_update', args=[self.scale.pk]),
            reverse('scale_delete', args=[self.scale.pk]),
            reverse('client_detail', args=[self.client_entity.pk]),
            reverse('client_update', args=[self.client_entity.pk]),
            reverse('service_order', args=[self.client_entity.pk, self.scale.pk]),
            reverse('list_os'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertIn(
                response.status_code, (301, 302),
                msg=f'Página sem login deveria redirecionar: {url} (status {response.status_code})',
            )
            login_url = reverse('login')
            self.assertIn(login_url, response.url if response.url else '')


class TechnicalReportFlowTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.scale.scale_type = Scale.TYPE_ROAD
        self.scale.save(update_fields=['scale_type'])
        self.order = ServiceOrder.objects.create(
            tenant=self.tenant,
            client=self.client_entity,
            scale=self.scale,
            user=self.user,
        )
        self.client.force_login(self.user)

    def _measurement_data(self, prefix, total):
        data = {
            f'{prefix}-TOTAL_FORMS': str(total),
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
        }
        for index in range(total):
            data.update({
                f'{prefix}-{index}-sequence': str(index + 1),
                f'{prefix}-{index}-load_kg': '1000',
                f'{prefix}-{index}-indication_kg': '1000',
                f'{prefix}-{index}-error_kg': '0',
                f'{prefix}-{index}-ema_kg': '20',
            })
        return data

    def test_relatorio_rodoviario_conclui_com_31_medicoes(self):
        payload = {
            'action': 'complete',
            'service_type': 'REPARO',
            'truck_plate_snapshot': 'ABC1D23',
        }
        for prefix, total in (
            ('fidelitytest', 3), ('eccentricitytest', 6), ('weighingtest', 22)
        ):
            payload.update(self._measurement_data(prefix, total))

        response = self.client.post(reverse('technical_report', args=[self.order.pk]), payload)
        self.assertRedirects(response, reverse('technical_report_print', args=[self.order.pk]))
        report = TechnicalReport.objects.get(service_order=self.order)
        self.assertEqual(report.status, TechnicalReport.STATUS_COMPLETED)
        self.assertEqual(report.number, 1)
        self.assertEqual(report.truck_plate_snapshot, 'ABC1D23')
        self.assertEqual(report.fidelity_tests.count(), 3)
        self.assertEqual(report.fidelity_tests.get(sequence=1).error_kg, 0)
        self.assertEqual(report.eccentricity_tests.count(), 6)
        self.assertEqual(report.weighing_tests.count(), 22)
        printed = self.client.get(reverse('technical_report_print', args=[self.order.pk]))
        self.assertEqual(printed.status_code, 200)
        self.assertContains(printed, 'Ensaio de excentricidade')

    def test_lista_relatorios_exibe_numero_proprio(self):
        TechnicalReport.objects.create(
            service_order=self.order,
            tenant=self.tenant,
            number=7,
        )
        response = self.client.get(reverse('technical_report_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '#00007')

    def test_relatorio_ferroviario_fica_disponivel(self):
        self.scale.scale_type = Scale.TYPE_RAIL
        self.scale.save(update_fields=['scale_type'])
        response = self.client.get(reverse('technical_report', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)

    def test_relatorio_sem_classificacao_nao_fica_disponivel(self):
        self.scale.scale_type = None
        self.scale.save(update_fields=['scale_type'])
        response = self.client.get(reverse('technical_report', args=[self.order.pk]))
        self.assertRedirects(response, reverse('os_detail', args=[self.order.pk]))


class AccountFlowTests(TestCase):
    def test_register_login_logout(self):
        response = self.client.post(reverse('register'), {
            'email': 'novotecnico@example.com',
            'password1': 'senhaComplexa123',
            'password2': 'senhaComplexa123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='novotecnico@example.com').exists())

        response = self.client.post(reverse('login'), {
            'email': 'novotecnico@example.com',
            'password': 'senhaComplexa123',
        })
        self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_login_invalido_nao_quebra(self):
        response = self.client.post(reverse('login'), {
            'email': 'naoexiste@example.com',
            'password': 'errada',
        })
        self.assertEqual(response.status_code, 200)


class ClientTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.client_http = self.client
        self.client_http.force_login(self.user)

    def test_list_clientes(self):
        response = self.client_http.get(reverse('search_client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)

    def test_busca_cliente(self):
        response = self.client_http.get(reverse('search_client'), {'search': '12345678000100'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)

    def test_criar_cliente(self):
        response = self.client_http.post(reverse('new_client'), {
            'name': 'Cliente Beta',
            'document': '98765432000100',
            'state_registration': '',
            'address': '',
            'city': 'São Paulo',
            'uf': 'SP',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(document='98765432000100').exists())

    def test_documento_duplicado_rejeitado(self):
        response = self.client_http.post(reverse('new_client'), {
            'name': 'Cliente Duplicado',
            'document': self.client_entity.document,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui cadastro')
        self.assertEqual(Client.objects.filter(document=self.client_entity.document).count(), 1)

    def test_detalhe_cliente(self):
        response = self.client_http.get(reverse('client_detail', args=[self.client_entity.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)

    def test_atualizar_cliente(self):
        response = self.client_http.post(
            reverse('client_update', args=[self.client_entity.pk]),
            {'name': 'Cliente Alfa Atualizado', 'document': self.client_entity.document},
        )
        self.assertEqual(response.status_code, 302)
        self.client_entity.refresh_from_db()
        self.assertEqual(self.client_entity.name, 'Cliente Alfa Atualizado')


class ScaleTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.client_http = self.client
        self.client_http.force_login(self.user)

    def test_list_balancas(self):
        response = self.client_http.get(reverse('search_scale'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.scale.brand)

    def test_busca_balanca_por_serie(self):
        response = self.client_http.get(reverse('search_scale'), {'search': 'SER-001'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SER-001')

    def test_criar_balanca(self):
        response = self.client_http.post(reverse('new_scale'), {
            'brand': 'Filizola',
            'model': 'BC',
            'serie': 'SER-002',
            'capacity': '150',
            'unit': self.unit_kg.pk,
            'division': '0.02',
            'client': self.client_entity.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Scale.objects.filter(serie='SER-002').exists())

    def test_serie_duplicada_para_mesmo_cliente_rejeitada(self):
        response = self.client_http.post(reverse('new_scale'), {
            'brand': 'Outra',
            'model': 'X',
            'serie': self.scale.serie,
            'capacity': '300',
            'unit': self.unit_kg.pk,
            'division': '0.05',
            'client': self.client_entity.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui cadastro')

    def test_detalhe_balanca(self):
        response = self.client_http.get(reverse('scale_detail', args=[self.scale.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.scale.brand)

    def test_atualizar_balanca(self):
        response = self.client_http.post(
            reverse('scale_update', args=[self.scale.pk]),
            {'brand': 'Toledo Atualizada', 'model': self.scale.model, 'serie': 'SER-001',
             'capacity': '300', 'unit': self.unit_kg.pk, 'division': '0.05', 'client': self.client_entity.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.scale.refresh_from_db()
        self.assertEqual(self.scale.brand, 'Toledo Atualizada')

    def test_excluir_balanca(self):
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('scale_delete', args=[self.scale.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Scale.objects.filter(pk=self.scale.pk).exists())

    def test_tecnico_pode_criar_balanca(self):
        self.client_http.force_login(self.technician)
        response = self.client_http.post(reverse('new_scale'), {
            'brand': 'Filizola',
            'model': 'BC',
            'serie': 'SER-NOVO',
            'capacity': '150',
            'unit': self.unit_kg.pk,
            'division': '0.02',
            'client': self.client_entity.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Scale.objects.filter(serie='SER-NOVO').exists())


class ServiceOrderTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.client_http = self.client
        self.client_http.force_login(self.user)

    def stamp_delivery(self):
        stamp = Stamp.objects.create(number='SELO-1', tenant=self.tenant)
        return StampDelivery.objects.create(
            number=stamp, user=self.user, status='AVAILABLE', tenant=self.tenant
        )

    def service_order_payload(self, stamp_id=''):
        data = {
            'signature': '',
            'observation': 'Serviço de teste',
            'stamp_retired': 'SELO-RETIRADO-1',
            'stamp': str(stamp_id) if stamp_id else '',
            'service1': 'on',
            'verified': 'on',
            'new_instalation': '',
            'host': '',
            'food': '',
            'service_order_part-TOTAL_FORMS': '1',
            'service_order_part-INITIAL_FORMS': '0',
            'service_order_part-MIN_NUM_FORMS': '0',
            'service_order_part-MAX_NUM_FORMS': '1000',
            'service_order_part-0-code': '123',
            'service_order_part-0-amount': '2',
            'service_order_part-0-serie': 'PART-SERIE',
            'service_order_part-0-description': 'Peça de teste',
            'service_order_part-0-base': 'on',
            'service_order_part-0-service_order': '',
            'time_service-TOTAL_FORMS': '1',
            'time_service-INITIAL_FORMS': '0',
            'time_service-MIN_NUM_FORMS': '0',
            'time_service-MAX_NUM_FORMS': '1000',
            'time_service-0-day': str(date.today()),
            'time_service-0-start': '08:00',
            'time_service-0-stop': '12:00',
            'time_service-0-total_hours': '04:00',
            'time_service-0-car': 'CAR-1',
            'time_service-0-truck': '',
            'time_service-0-service_order': '',
        }
        return data

    def test_form_os_abre(self):
        response = self.client_http.get(reverse('service_order', args=[self.client_entity.pk, self.scale.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)
        self.assertContains(response, self.scale.brand)

    def test_criar_os_completa(self):
        stamp_delivery = self.stamp_delivery()
        response = self.client_http.post(
            reverse('service_order', args=[self.client_entity.pk, self.scale.pk]),
            self.service_order_payload(stamp_delivery.pk),
        )
        self.assertEqual(response.status_code, 302)

        os = ServiceOrder.objects.get(client=self.client_entity, scale=self.scale)
        self.assertEqual(os.user, self.user)
        self.assertTrue(os.service1)
        self.assertTrue(os.verified)
        self.assertEqual(Part.objects.filter(service_order=os).count(), 1)
        self.assertEqual(TimeService.objects.filter(service_order=os).count(), 1)
        stamp_delivery.refresh_from_db()
        self.assertEqual(stamp_delivery.status, 'USED')

    def test_criar_os_sem_selo(self):
        response = self.client_http.post(
            reverse('service_order', args=[self.client_entity.pk, self.scale.pk]),
            self.service_order_payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceOrder.objects.filter(client=self.client_entity).exists())

    def test_lista_os_filtra_por_usuario(self):
        os_tec = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.technician, tenant=self.tenant
        )
        os_staff = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )

        self.client_http.force_login(self.technician)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_tec.id}')
        self.assertNotContains(response, f'#{os_staff.id}')

        self.client_http.force_login(self.user)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_staff.id}')
        self.assertContains(response, f'#{os_tec.id}')

        self.client_http.force_login(self.superuser)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_staff.id}')

    def test_busca_os_por_numero(self):
        os = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        response = self.client_http.get(reverse('list_os'), {'search': str(os.id)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os.id}')

    def test_detalhe_os(self):
        os = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        response = self.client_http.get(reverse('os_detail', args=[os.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)

    def test_detalhe_os_usa_tenant_no_cabecalho(self):
        os = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )

        response = self.client_http.get(reverse('os_detail', args=[os.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tenant.name)

    def test_editar_os(self):
        os = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        stamp_delivery = self.stamp_delivery()
        data = self.service_order_payload(stamp_delivery.pk)
        data.update({
            'service2': 'on',
            'observation': 'Ordem atualizada',
            'service_order_part-0-code': '999',
            'service_order_part-0-amount': '5',
            'service_order_part-0-serie': 'SERIE-NOVA',
            'service_order_part-0-description': 'Peça nova',
            'service_order_part-0-base': '',
            'service_order_part-0-service_order': os.pk,
            'time_service-0-day': str(date.today()),
            'time_service-0-start': '09:00',
            'time_service-0-stop': '13:00',
            'time_service-0-total_hours': '04:00',
            'time_service-0-car': '',
            'time_service-0-truck': '',
            'time_service-0-service_order': os.pk,
        })
        response = self.client_http.post(reverse('os_update', args=[os.pk]), data)
        self.assertEqual(response.status_code, 302)
        os.refresh_from_db()
        self.assertEqual(os.observation, 'Ordem atualizada')
        self.assertTrue(os.service2)
        self.assertEqual(Part.objects.filter(service_order=os).count(), 1)


class RowClickRegressionTests(BaseSetup, TestCase):
    """Garante que as linhas das listas continuam com data-href apontando ao detalhe."""

    def setUp(self):
        self.create_base()
        self.client_http = self.client
        self.client_http.force_login(self.user)

    def test_lista_os_tem_data_href(self):
        os = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-href="{reverse("os_detail", args=[os.pk])}"')

    def test_lista_clientes_tem_data_href(self):
        response = self.client_http.get(reverse('search_client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-href="{reverse("client_detail", args=[self.client_entity.pk])}"')

    def test_lista_balancas_tem_data_href(self):
        response = self.client_http.get(reverse('search_scale'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-href="{reverse("scale_detail", args=[self.scale.pk])}"')


class TenantIsolationTests(BaseSetup, TestCase):
    """Tenant A não enxerga cadastros do tenant B."""

    def setUp(self):
        self.create_base()
        self.tenant_b = Tenant.objects.create(
            name='Empresa Beta', document='98765432000199'
        )
        self.user_b = User.objects.create_user(
            email='beta@example.com',
            password='senha123',
            tenant=self.tenant_b,
            role='STAFF',
        )
        self.unit_b = Unit.objects.create(name='lb', tenant=self.tenant_b)
        self.client_b = Client.objects.create(
            name='Cliente Beta',
            document='98765432000100',
            tenant=self.tenant_b,
        )
        self.scale_b = Scale.objects.create(
            brand='Filizola',
            model='BC',
            serie='SER-B-001',
            capacity='150',
            unit=self.unit_b,
            division='0.02',
            client=self.client_b,
            tenant=self.tenant_b,
        )
        self.client_http = self.client

    def test_lista_clientes_isolada(self):
        self.client_http.force_login(self.user)
        response = self.client_http.get(reverse('search_client'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)
        self.assertNotContains(response, self.client_b.name)

    def test_lista_balancas_isolada(self):
        self.client_http.force_login(self.user)
        response = self.client_http.get(reverse('search_scale'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.scale.brand)
        self.assertNotContains(response, self.scale_b.brand)

    def test_detalhe_cliente_de_outro_tenant_404(self):
        self.client_http.force_login(self.user)
        response = self.client_http.get(
            reverse('client_detail', args=[self.client_b.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_detalhe_balanca_de_outro_tenant_404(self):
        self.client_http.force_login(self.user)
        response = self.client_http.get(
            reverse('scale_detail', args=[self.scale_b.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_criar_cliente_atribui_tenant_do_usuario(self):
        self.client_http.force_login(self.user)
        self.client_http.post(reverse('new_client'), {
            'name': 'Cliente Alpha Dois',
            'document': '11223344000155',
            'city': 'Curitiba',
            'uf': 'PR',
        })
        novo = Client.objects.get(document='11223344000155')
        self.assertEqual(novo.tenant_id, self.tenant.pk)

    def test_documento_igual_em_tenants_diferentes_permitido(self):
        self.client_http.force_login(self.user_b)
        response = self.client_http.post(reverse('new_client'), {
            'name': 'Cliente Beta Dois',
            'document': self.client_entity.document,
            'city': 'São Paulo',
            'uf': 'SP',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Client.objects.filter(
                document=self.client_entity.document, tenant=self.tenant_b
            ).exists()
        )
        self.assertEqual(
            Client.objects.filter(document=self.client_entity.document).count(),
            2,
        )

    def test_tecnico_pode_criar_cliente(self):
        self.client_http.force_login(self.technician)
        response = self.client_http.post(reverse('new_client'), {
            'name': 'Sem Permissão',
            'document': '55667788000100',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(document='55667788000100').exists())


class StampServiceTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.client_http = self.client

    def test_distribuir_selo_transicao(self):
        stamp = Stamp.objects.create(number='SELO-10', tenant=self.tenant)
        delivery = distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)
        stamp.refresh_from_db()
        self.assertEqual(stamp.status, 'DISTRIBUTED')
        self.assertEqual(delivery.status, 'AVAILABLE')
        self.assertEqual(delivery.tenant_id, self.tenant.pk)

    def test_distribuir_selo_indisponivel_rejeitado(self):
        stamp = Stamp.objects.create(
            number='SELO-11', tenant=self.tenant, status='DISTRIBUTED'
        )
        with self.assertRaises(Exception):
            distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)

    def test_consumo_selo_unico(self):
        stamp = Stamp.objects.create(number='SELO-12', tenant=self.tenant)
        delivery = distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)
        os1 = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        consume_stamp_for_os(delivery_id=delivery.pk, service_order=os1)
        delivery.refresh_from_db()
        os1.refresh_from_db()
        self.assertEqual(delivery.status, 'USED')
        self.assertEqual(os1.stamp_id, delivery.pk)

        os2 = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        with self.assertRaises(Exception):
            consume_stamp_for_os(delivery_id=delivery.pk, service_order=os2)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'USED')

    def test_danificar_selo(self):
        stamp = Stamp.objects.create(number='SELO-13', tenant=self.tenant)
        delivery = distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)
        damage_delivery(delivery_id=delivery.pk, tenant=self.tenant)
        stamp.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(stamp.status, 'DAMAGED')
        self.assertEqual(delivery.status, 'DAMAGED')

    def test_listagem_selos_admin(self):
        self.client_http.force_login(self.admin)
        response = self.client_http.get(reverse('stamp_list'))
        self.assertEqual(response.status_code, 200)

    def test_listagem_selos_tecnico_negado(self):
        self.client_http.force_login(self.technician)
        response = self.client_http.get(reverse('stamp_list'))
        self.assertEqual(response.status_code, 403)

    def test_admin_cadastra_selo(self):
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_create'), {'number': 'SELO-NEW'})
        self.assertEqual(response.status_code, 302)
        stamp = Stamp.objects.get(number='SELO-NEW')
        self.assertEqual(stamp.tenant, self.tenant)
        self.assertEqual(stamp.status, 'AVAILABLE')

    def test_admin_cadastra_selos_em_lote(self):
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_create'), {
            'numbers': 'SELO-LOTE-01\nSELO-LOTE-02, SELO-LOTE-03',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Stamp.objects.filter(number__startswith='SELO-LOTE-', tenant=self.tenant).count(),
            3,
        )

    def test_tecnico_nao_cadastra_selo(self):
        self.client_http.force_login(self.technician)
        response = self.client_http.get(reverse('stamp_create'))
        self.assertEqual(response.status_code, 403)

    def test_admin_distribui_selos_em_lote(self):
        stamps = [
            Stamp.objects.create(number=f'SELO-B-{index}', tenant=self.tenant)
            for index in range(1, 4)
        ]
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_bulk_distribute'), {
            'user': self.technician.pk,
            'stamps': [stamp.pk for stamp in stamps],
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            StampDelivery.objects.filter(user=self.technician, tenant=self.tenant).count(),
            3,
        )

    def test_distribuicao_em_lote_exige_selecao(self):
        stamp = Stamp.objects.create(number='SELO-B-VALIDO', tenant=self.tenant)
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_bulk_distribute'), {
            'user': self.technician.pk,
            'stamps': [],
        })
        self.assertEqual(response.status_code, 200)
        stamp.refresh_from_db()
        self.assertEqual(stamp.status, 'AVAILABLE')
        self.assertFalse(StampDelivery.objects.filter(number=stamp).exists())

    def test_distribuir_via_view(self):
        stamp = Stamp.objects.create(number='SELO-14', tenant=self.tenant)
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_distribute'), {
            'number': stamp.pk,
            'user': self.technician.pk,
        })
        self.assertEqual(response.status_code, 302)
        stamp.refresh_from_db()
        self.assertEqual(stamp.status, 'DISTRIBUTED')
        self.assertTrue(
            StampDelivery.objects.filter(number=stamp, user=self.technician).exists()
        )

    def test_danificar_via_view(self):
        stamp = Stamp.objects.create(number='SELO-15', tenant=self.tenant)
        delivery = distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)
        self.client_http.force_login(self.admin)
        response = self.client_http.post(reverse('stamp_damage', args=[delivery.pk]))
        self.assertEqual(response.status_code, 302)
        stamp.refresh_from_db()
        self.assertEqual(stamp.status, 'DAMAGED')

    def test_next_os_number_sequencial_sem_duplicatas(self):
        numbers = []
        for _ in range(5):
            n = next_os_number(self.tenant)
            ServiceOrder.objects.create(
                client=self.client_entity,
                scale=self.scale,
                user=self.user,
                tenant=self.tenant,
                number=n,
            )
            numbers.append(n)

        self.assertEqual(len(set(numbers)), 5)
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(numbers, [1, 2, 3, 4, 5])

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ServiceOrder.objects.create(
                    client=self.client_entity,
                    scale=self.scale,
                    user=self.user,
                    tenant=self.tenant,
                    number=numbers[0],
                )

    def test_os_create_via_view_recebe_numero_e_selo(self):
        stamp = Stamp.objects.create(number='SELO-16', tenant=self.tenant)
        delivery = distribute_stamp(stamp=stamp, user=self.user, tenant=self.tenant)
        self.client_http.force_login(self.user)

        payload = {
            'signature': 'data:image/png;base64,AAAA',
            'observation': 'Numeração e selo',
            'stamp_retired': '',
            'stamp': str(delivery.pk),
            'service1': 'on',
            'verified': 'on',
            'new_instalation': '',
            'host': '',
            'food': '',
            'service_order_part-TOTAL_FORMS': '0',
            'service_order_part-INITIAL_FORMS': '0',
            'service_order_part-MIN_NUM_FORMS': '0',
            'service_order_part-MAX_NUM_FORMS': '1000',
            'time_service-TOTAL_FORMS': '0',
            'time_service-INITIAL_FORMS': '0',
            'time_service-MIN_NUM_FORMS': '0',
            'time_service-MAX_NUM_FORMS': '1000',
        }
        response = self.client_http.post(
            reverse('service_order', args=[self.client_entity.pk, self.scale.pk]),
            payload,
        )
        self.assertEqual(response.status_code, 302)
        os = ServiceOrder.objects.get(stamp=delivery)
        self.assertIsNotNone(os.number)
        self.assertEqual(os.tenant_id, self.tenant.pk)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'USED')
        self.assertTrue(os.signature.startswith('data:image/png'))


class PermissionMatrixTests(BaseSetup, TestCase):
    """Cobertura da matriz §8.9 (células do MVP; IA v1.1 fora desta sprint)."""

    def setUp(self):
        self.create_base()
        self.client_http = self.client

    def _login(self, user):
        self.client_http.force_login(user)
        return self.client_http

    def test_ver_suas_os_todos_os_perfis(self):
        os_own = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        for user in (self.technician, self.user, self.admin, self.superuser):
            self._login(user)
            if user == self.technician:
                os_tec = ServiceOrder.objects.create(
                    client=self.client_entity, scale=self.scale, user=self.technician, tenant=self.tenant
                )
                response = self.client_http.get(reverse('os_detail', args=[os_tec.pk]))
                self.assertEqual(response.status_code, 200, user.email)
            else:
                response = self.client_http.get(reverse('os_detail', args=[os_own.pk]))
                self.assertEqual(response.status_code, 200, user.email)

    def test_tecnico_nao_ve_os_de_outro_tecnico(self):
        os_other = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        self._login(self.technician)
        response = self.client_http.get(reverse('os_detail', args=[os_other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_staff_ve_todas_os_do_tenant_na_lista(self):
        os_other = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.technician, tenant=self.tenant
        )
        self._login(self.user)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_other.id}')

    def test_tecnico_lista_so_as_proprias(self):
        os_tec = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.technician, tenant=self.tenant
        )
        os_staff = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        self._login(self.technician)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_tec.id}')
        self.assertNotContains(response, f'#{os_staff.id}')

    def test_criar_os_todos_os_perfis(self):
        for user in (self.technician, self.user, self.admin):
            self._login(user)
            response = self.client_http.get(
                reverse('service_order', args=[self.client_entity.pk, self.scale.pk])
            )
            self.assertEqual(response.status_code, 200, user.email)

    def test_editar_os_permitido_para_tecnico(self):
        os_obj = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.technician, tenant=self.tenant
        )
        self._login(self.technician)
        response = self.client_http.get(reverse('os_update', args=[os_obj.pk]))
        self.assertEqual(response.status_code, 200)

    def test_editar_os_permitido_para_staff_e_admin(self):
        for user in (self.user, self.admin):
            os_obj = ServiceOrder.objects.create(
                client=self.client_entity, scale=self.scale, user=user, tenant=self.tenant
            )
            self._login(user)
            response = self.client_http.get(reverse('os_update', args=[os_obj.pk]))
            self.assertEqual(response.status_code, 200, user.email)

    def test_crud_clientes_permitido_para_tecnico(self):
        self._login(self.technician)
        self.assertEqual(
            self.client_http.get(reverse('new_client')).status_code, 200
        )
        self.assertEqual(
            self.client_http.get(reverse('new_scale')).status_code, 200
        )

    def test_crud_clientes_permitido_para_staff_e_admin(self):
        for user in (self.user, self.admin):
            self._login(user)
            self.assertEqual(
                self.client_http.get(reverse('new_client')).status_code, 200, user.email
            )
            self.assertEqual(
                self.client_http.get(reverse('new_scale')).status_code, 200, user.email
            )

    def test_distribuir_selos_apenas_admin(self):
        self._login(self.technician)
        self.assertEqual(self.client_http.get(reverse('stamp_list')).status_code, 403)
        self.assertEqual(self.client_http.get(reverse('stamp_distribute')).status_code, 403)

        self._login(self.user)
        self.assertEqual(self.client_http.get(reverse('stamp_list')).status_code, 403)

        self._login(self.admin)
        self.assertEqual(self.client_http.get(reverse('stamp_list')).status_code, 200)
        self.assertEqual(self.client_http.get(reverse('stamp_distribute')).status_code, 200)

    def test_excluir_os_negado_para_tecnico_da_propria_os(self):
        os_obj = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.technician,
            tenant=self.tenant,
        )
        self.client_http.force_login(self.technician)
        response = self.client_http.post(reverse('os_delete', args=[os_obj.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ServiceOrder.objects.filter(pk=os_obj.pk).exists())

    def test_print_rota_autenticada(self):
        os_obj = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        self.client_http.force_login(self.user)
        response = self.client_http.get(reverse('os_print', args=[os_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ordem de Serviço')

    def test_print_negado_sem_login(self):
        from django.test import Client as AnonClient

        anon = AnonClient()
        os_obj = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        response = anon.get(reverse('os_print', args=[os_obj.pk]))
        self.assertEqual(response.status_code, 302)

    def test_lista_os_filtro_data(self):
        os_obj = ServiceOrder.objects.create(
            client=self.client_entity, scale=self.scale, user=self.user, tenant=self.tenant
        )
        self._login(self.user)
        response = self.client_http.get(reverse('list_os'), {'date_filter': os_obj.date.date().isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'{os_obj.id}')
