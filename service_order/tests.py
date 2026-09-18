from datetime import date
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from service_order.models import Client, Company, Part, Scale, ServiceOrder, Stamp, StampDelivery, TimeService, Unit


def make_logo_image(name='logo.png'):
    buffer = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class BaseSetup:
    def create_base(self):
        self.user = User.objects.create_user(username='tecnico', password='senha123')
        self.superuser = User.objects.create_superuser(username='admin', password='senha123', email='admin@x.com')
        self.unit_kg = Unit.objects.create(name='kg')
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


class AccountFlowTests(TestCase):
    def test_register_login_logout(self):
        response = self.client.post(reverse('register'), {
            'username': 'novotecnico',
            'password1': 'senhaComplexa123',
            'password2': 'senhaComplexa123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='novotecnico').exists())

        response = self.client.post(reverse('login'), {
            'username': 'novotecnico',
            'password': 'senhaComplexa123',
        })
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_login_invalido_nao_quebra(self):
        response = self.client.post(reverse('login'), {
            'username': 'naoexiste',
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
        response = self.client_http.post(reverse('scale_delete', args=[self.scale.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Scale.objects.filter(pk=self.scale.pk).exists())


class ServiceOrderTests(BaseSetup, TestCase):
    def setUp(self):
        self.create_base()
        self.client_http = self.client
        self.client_http.force_login(self.user)

    def stamp_delivery(self):
        stamp = Stamp.objects.create(number='SELO-1')
        return StampDelivery.objects.create(number=stamp, user=self.user, status='DISPONIVEL')

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
        self.assertEqual(stamp_delivery.status, 'UTILIZADO')

    def test_criar_os_sem_selo(self):
        response = self.client_http.post(
            reverse('service_order', args=[self.client_entity.pk, self.scale.pk]),
            self.service_order_payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceOrder.objects.filter(client=self.client_entity).exists())

    def test_lista_os_filtra_por_usuario(self):
        another = User.objects.create_user(username='outro', password='senha123')
        os_user = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)
        os_other = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=another)

        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_user.id}')
        self.assertNotContains(response, f'#{os_other.id}')

        self.client_http.force_login(self.superuser)
        response = self.client_http.get(reverse('list_os'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os_other.id}')

    def test_busca_os_por_numero(self):
        os = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)
        response = self.client_http.get(reverse('list_os'), {'search': str(os.id)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'#{os.id}')

    def test_detalhe_os(self):
        os = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)
        Company.objects.create(
            name='Empresa Certa',
            document='00000000000100',
            address='Rua',
            city='Curitiba',
            uf='PR',
            contact='41 0000-0000',
            logo=make_logo_image(),
        )
        Company.objects.create(
            name='Empresa Errada',
            document='00000000000200',
            address='Rua',
            city='Curitiba',
            uf='PR',
            contact='41 0000-0000',
            logo=make_logo_image(),
        )

        response = self.client_http.get(reverse('os_detail', args=[os.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_entity.name)

    def test_detalhe_os_sem_empresa_cadastrada(self):
        os = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)

        response = self.client_http.get(reverse('os_detail', args=[os.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nenhuma empresa cadastrada')

    def test_editar_os(self):
        os = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)
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
        os = ServiceOrder.objects.create(client=self.client_entity, scale=self.scale, user=self.user)
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