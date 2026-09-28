from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.backends import EmailBackend
from accounts.models import User
from core.managers import TenantManager
from core.models import TenantScopedModel, get_current_tenant, set_current_tenant
from core.permissions import AdminRequiredMixin, RoleRequiredMixin, StaffRequiredMixin
from tenants.middleware import TenantMiddleware
from tenants.models import Tenant


class EmailAuthTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Empresa Alpha', document='11111111000111')
        self.user = User.objects.create_user(
            email='tecnico@example.com', password='SenhaForte123', tenant=self.tenant
        )

    def test_login_por_email(self):
        response = self.client.post(reverse('login'), {
            'email': 'tecnico@example.com',
            'password': 'SenhaForte123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_login_email_incorreto_falha(self):
        response = self.client.post(reverse('login'), {
            'email': 'outro@example.com',
            'password': 'SenhaForte123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_email_backend_authenticate(self):
        backend = EmailBackend()
        user = backend.authenticate(None, username='tecnico@example.com', password='SenhaForte123')
        self.assertEqual(user, self.user)
        self.assertIsNone(
            backend.authenticate(None, username='tecnico@example.com', password='errada')
        )

    def test_email_unico(self):
        with self.assertRaises(Exception):
            User.objects.create_user(email='tecnico@example.com', password='x')


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(name='Empresa Beta', document='22222222000122')
        self.user = User.objects.create_user(
            email='admin@example.com', password='SenhaForte123', tenant=self.tenant
        )

    def _middleware_response(self, request):
        def get_response(req):
            req.captured_tenant = getattr(req, 'tenant', None)
            return req.captured_tenant

        return TenantMiddleware(get_response)(request)

    def test_middleware_coloca_request_tenant(self):
        request = self.factory.get('/')
        request.user = self.user
        tenant = self._middleware_response(request)
        self.assertEqual(tenant, self.tenant)

    def test_middleware_anonimo_tenant_none(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/')
        request.user = AnonymousUser()
        tenant = self._middleware_response(request)
        self.assertIsNone(tenant)

    def test_contextvar_limpa_apos_request(self):
        request = self.factory.get('/')
        request.user = self.user
        self._middleware_response(request)
        self.assertIsNone(get_current_tenant())


class AccessDeniedTests(TestCase):
    def test_rota_protegida_redireciona_sem_login(self):
        response = self.client.get(reverse('home'))
        self.assertIn(response.status_code, (301, 302))
        self.assertIn(reverse('login'), response.url)


class RoleMixinTests(TestCase):
    def _view_class(self, mixin):
        class DummyView(mixin):
            roles = getattr(mixin, 'roles', None)

            def get(self, request):
                return None

        return DummyView

    def test_staff_requer_staff_ou_admin(self):
        tenant = Tenant.objects.create(name='G', document='33333333000133')
        tech = User.objects.create_user(email='t@e.com', password='x', role='TECHNICIAN', tenant=tenant)
        staff = User.objects.create_user(email='s@e.com', password='x', role='STAFF', tenant=tenant)
        admin = User.objects.create_user(email='a@e.com', password='x', role='ADMIN', tenant=tenant)

        factory = RequestFactory()
        View = self._view_class(StaffRequiredMixin)
        v = View()
        request = factory.get('/')

        request.user = tech
        v.request = request
        self.assertFalse(v.test_func())

        request.user = staff
        v.request = request
        self.assertTrue(v.test_func())

        request.user = admin
        v.request = request
        self.assertTrue(v.test_func())

    def test_admin_requer_admin(self):
        tenant = Tenant.objects.create(name='H', document='44444444000144')
        staff = User.objects.create_user(email='s2@e.com', password='x', role='STAFF', tenant=tenant)
        admin = User.objects.create_user(email='a2@e.com', password='x', role='ADMIN', tenant=tenant)

        factory = RequestFactory()
        View = self._view_class(AdminRequiredMixin)
        v = View()

        request = factory.get('/')
        request.user = staff
        v.request = request
        self.assertFalse(v.test_func())

        request.user = admin
        v.request = request
        self.assertTrue(v.test_func())

    def test_superuser_passa_sempre(self):
        su = User.objects.create_superuser(email='su@e.com', password='x')
        factory = RequestFactory()
        View = self._view_class(RoleRequiredMixin)
        v = View()
        request = factory.get('/')
        request.user = su
        v.request = request
        self.assertTrue(v.test_func())


class TenantScopedModelTests(TestCase):
    def test_manager_escopo_e_contextvar(self):
        from django.db import models

        class Probe(TenantScopedModel):
            name = models.CharField(max_length=50)

            class Meta:
                app_label = 'core'

        self.assertIsInstance(Probe.objects, models.Manager)
        self.assertIsInstance(Probe.scoped, TenantManager)
        self.assertIsNone(get_current_tenant())

        t1 = Tenant.objects.create(name='T1', document='55555555000155')
        token = set_current_tenant(t1)
        try:
            self.assertEqual(get_current_tenant(), t1)
        finally:
            from core.models import reset_current_tenant

            reset_current_tenant(token)
        self.assertIsNone(get_current_tenant())
