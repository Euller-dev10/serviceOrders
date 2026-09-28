from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tenants.models import Plan, Subscription, Tenant

User = get_user_model()


class InviteFlowBase(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.tenant = Tenant.objects.create(name='Zeta Ltda', document='77788899000111')
        self.admin = User.objects.create_user(
            email='admin@zeta.test', password='SenhaForte', role='ADMIN',
            tenant=self.tenant,
        )
        self.tech = User.objects.create_user(
            email='tech@zeta.test', password='SenhaForte', role='TECHNICIAN',
            tenant=self.tenant,
        )

    def make_plan(self, max_technicians):
        plan = Plan.objects.create(
            code='invite-plan', name='Plano Convite', max_technicians=max_technicians
        )
        now = timezone.now()
        Subscription.objects.create(
            tenant=self.tenant, plan=plan, status=Subscription.STATUS_ACTIVE,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
        return plan

    def create_invited_user(self, email='novo@zeta.test', token='tok-1'):
        return User.objects.create_user(
            email=email, password='OldPass123', tenant=self.tenant,
            role='TECHNICIAN', is_active=False, invite_token=token,
            invite_expires_at=timezone.now() + timedelta(hours=72),
        )


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InviteCreationTests(InviteFlowBase):
    def test_convite_cria_usuario_inativo_e_envia_email(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('user_invite'), {
            'email': 'novo@zeta.test',
            'first_name': 'Novo',
            'last_name': 'Técnico',
            'role': 'TECHNICIAN',
            'phone': '',
        })
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(email='novo@zeta.test')
        self.assertFalse(user.is_active)
        self.assertTrue(user.invite_token)
        self.assertLessEqual(
            user.invite_expires_at - timezone.now(), timedelta(hours=72, seconds=1)
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Convite', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['novo@zeta.test'])

    def test_convite_email_duplicado_falha(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('user_invite'), {
            'email': 'tech@zeta.test', 'role': 'TECHNICIAN',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            User.objects.filter(email='tech@zeta.test').count(), 1
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_convite_tecnico_recebe_403(self):
        self.client.force_login(self.tech)
        self.assertEqual(self.client.get(reverse('user_invite')).status_code, 403)
        self.assertEqual(self.client.get(reverse('user_list')).status_code, 403)

    def test_convite_seat_limit_bloqueado(self):
        self.make_plan(max_technicians=1)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('user_invite'),
            {'email': 'outro@zeta.test', 'role': 'TECHNICIAN'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email='outro@zeta.test').exists())
        self.assertEqual(len(mail.outbox), 0)


class InviteAcceptTests(InviteFlowBase):
    def test_get_formulario_aceite(self):
        self.create_invited_user()
        response = self.client.get(reverse('invite_accept', args=['tok-1']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Defina sua senha')

    def test_aceite_valido_ativa_e_possa_logar(self):
        user = self.create_invited_user()
        response = self.client.post(
            reverse('invite_accept', args=['tok-1']),
            {'password1': 'SenhaBoa99', 'password2': 'SenhaBoa99'},
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.invite_token)
        self.assertTrue(user.check_password('SenhaBoa99'))
        self.assertTrue(self.client.login(email='novo@zeta.test', password='SenhaBoa99'))

    def test_aceite_senhas_diferentes_falha(self):
        user = self.create_invited_user()
        response = self.client.post(
            reverse('invite_accept', args=['tok-1']),
            {'password1': 'SenhaBoa99', 'password2': 'SenhaBoa98'},
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_aceite_token_expirado_invalido(self):
        user = self.create_invited_user()
        user.invite_expires_at = timezone.now() - timedelta(seconds=1)
        user.save(update_fields=['invite_expires_at'])

        response = self.client.get(reverse('invite_accept', args=['tok-1']))
        self.assertContains(response, 'inválido')

        response = self.client.post(
            reverse('invite_accept', args=['tok-1']),
            {'password1': 'SenhaBoa99', 'password2': 'SenhaBoa99'},
        )
        self.assertContains(response, 'inválido')
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_aceite_bloqueia_quando_assentos_no_limite(self):
        self.make_plan(max_technicians=1)
        self.create_invited_user()

        response = self.client.post(
            reverse('invite_accept', args=['tok-1']),
            {'password1': 'SenhaBoa99', 'password2': 'SenhaBoa99'},
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='novo@zeta.test')
        self.assertFalse(user.is_active)
        self.assertTrue(user.invite_token)


class UserEditTests(InviteFlowBase):
    def test_admin_edita_role(self):
        user = self.create_invited_user()
        self.client.force_login(self.admin)

        response = self.client.post(reverse('user_edit', args=[user.pk]), {
            'email': user.email, 'first_name': 'Novo', 'last_name': 'Técnico',
            'role': 'STAFF', 'phone': '4199999999', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.role, 'STAFF')
        self.assertTrue(user.is_active)

    def test_admin_nao_desativa_a_si_mesmo_como_ultimo_admin(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('user_edit', args=[self.admin.pk]), {
            'email': self.admin.email, 'first_name': '', 'last_name': '',
            'role': 'ADMIN', 'phone': '', 'is_active': '',
        })
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
