"""Auth por e-mail (legado), gestão de usuários do tenant (US-12) e aceite de convite."""

import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.forms import (
    EmailAuthenticationForm,
    EmailUserCreationForm,
    InviteAcceptForm,
    UserEditForm,
    UserInviteForm,
)
from core.permissions import admin_required


def register_view(request):
    if request.method == 'POST':
        user_form = EmailUserCreationForm(request.POST)
        if user_form.is_valid():
            user_form.save()
            return redirect('login')
    else:
        user_form = EmailUserCreationForm()
    return render(request, 'register.html', {'user_form': user_form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        rate_key = f'login-rate:{ip}'
        attempts = cache.get(rate_key, 0)
        if attempts >= getattr(settings, 'LOGIN_RATE_LIMIT_PER_WINDOW', 5):
            login_form = EmailAuthenticationForm(request, data=request.POST)
            login_form.add_error(
                None,
                'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.',
            )
            return render(request, 'login.html', {'login_form': login_form}, status=429)
        login_form = EmailAuthenticationForm(request, data=request.POST)
        if login_form.is_valid():
            cache.delete(rate_key)
            login(request, login_form.get_user())
            return redirect('home')
        cache.set(
            rate_key,
            attempts + 1,
            getattr(settings, 'LOGIN_RATE_WINDOW_SECONDS', 300),
        )
    else:
        login_form = EmailAuthenticationForm(request)
    return render(request, 'login.html', {'login_form': login_form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('login')


User = get_user_model()


def _tenant_of(request):
    return getattr(request, 'tenant', None) or getattr(request.user, 'tenant', None)


@admin_required
def user_list_view(request):
    tenant = _tenant_of(request)
    users = User.objects.filter(tenant=tenant).order_by('email')
    return render(request, 'user_list.html', {'users': users})


@admin_required
def user_invite_view(request):
    tenant = _tenant_of(request)
    if tenant is None:
        messages.error(request, 'Usuário sem tenant ativo.')
        return redirect('home')

    if request.method == 'POST':
        from tenants.services import seat_limit_reached

        if seat_limit_reached(tenant):
            messages.error(
                request,
                'Limite de assentos do plano atingido. '
                'Atualize o plano para convidar mais usuários.',
            )
            return redirect('user_list')
        form = UserInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'Este e-mail já está cadastrado.')
            else:
                user = form.save(commit=False)
                user.email = email
                user.tenant = tenant
                user.is_active = False
                user.set_unusable_password()
                user.invite_token = secrets.token_urlsafe(32)
                user.invite_expires_at = timezone.now() + timedelta(hours=72)
                user.save()
                from core.emails import send_invite_email

                invite_url = request.build_absolute_uri(
                    reverse('invite_accept', args=[user.invite_token])
                )
                sent = send_invite_email(user, invite_url)
                if sent:
                    messages.success(
                        request, f'Convite enviado para {user.email} (expira em 72h).'
                    )
                else:
                    messages.warning(
                        request,
                        f'Usuário criado para {user.email}, mas o e-mail de convite '
                        f'falhou no envio.',
                    )
                return redirect('user_list')
    else:
        form = UserInviteForm()
    return render(request, 'user_form.html', {'form': form, 'action': 'Convidar usuário'})


@admin_required
def user_edit_view(request, pk):
    tenant = _tenant_of(request)
    user_obj = get_object_or_404(User, pk=pk, tenant=tenant)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user_obj)
        if form.is_valid():
            was_active = User.objects.filter(pk=user_obj.pk).values_list(
                'is_active', flat=True
            ).first()
            becoming_inactive = bool(was_active and not form.cleaned_data.get('is_active'))
            if becoming_inactive:
                from tenants.services import count_active_admins

                if user_obj.role == 'ADMIN' and count_active_admins(tenant) <= 1:
                    form.add_error(
                        None, 'Não é possível desativar o último ADMIN do tenant.'
                    )
            if not form.errors:
                form.save()
                messages.success(request, f'Usuário {user_obj.email} atualizado.')
                return redirect('user_list')
    else:
        form = UserEditForm(instance=user_obj)
    return render(
        request,
        'user_form.html',
        {'form': form, 'action': 'Editar usuário', 'edited_user': user_obj},
    )


def invite_accept_view(request, token):
    """Definição de senha por convite (expira em 72h; libera o assento do plano)."""
    now = timezone.now()
    user = User.objects.filter(invite_token=token, invite_expires_at__gt=now).first()

    if user is None:
        return render(
            request,
            'invite_accept.html',
            {'invalid': True, 'form': InviteAcceptForm()},
        )

    if request.method == 'POST':
        form = InviteAcceptForm(request.POST)
        if form.is_valid():
            from tenants.services import seat_limit_reached

            if user.tenant is not None and seat_limit_reached(user.tenant):
                messages.error(
                    request,
                    'Não é possível ativar este acesso: limite de assentos do plano '
                    'foi atingido. Fale com o administrador.',
                )
                return redirect('login')
            user.set_password(form.cleaned_data['password2'])
            user.is_active = True
            user.invite_token = None
            user.invite_expires_at = None
            user.save()
            messages.success(request, 'Senha definida. Faça login para continuar.')
            return redirect('login')
    else:
        form = InviteAcceptForm()
    return render(request, 'invite_accept.html', {'user': user, 'form': form})
