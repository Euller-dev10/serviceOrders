"""E-mails transacionais (Sprint 3.2) — convite, O.S. assinada e limite de plano.

Todos os envios são best-effort: falha de SMTP registra log e nunca quebra o fluxo do usuário.
Backend real vem de `EMAIL_BACKEND` (console no MVP/dev; SMTP em produção via .env).
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PLAN_LIMIT_EMAIL_TTL_SECONDS = 24 * 3600

RESOURCE_LABELS = {
    'service_orders': 'Ordens de Serviço/mês',
    'seats': 'Assentos',
    'ai_credits': 'Créditos IA/mês',
}


def admin_recipients(tenant) -> list[str]:
    if tenant is None:
        return []
    emails = list(
        tenant.users.filter(role='ADMIN', is_active=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )
    if not emails and tenant.email:
        emails = [tenant.email]
    return emails


def _send(subject, body, recipients) -> int:
    if not recipients:
        return 0
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
        return 1
    except Exception:
        logger.exception('Falha ao enviar e-mail transacional: %s', subject)
        return 0


def send_os_signed_email(service_order) -> int:
    """Notifica os ADMINs do tenant que uma O.S. foi assinada pelo cliente."""
    tenant = getattr(service_order, 'tenant', None)
    recipients = admin_recipients(tenant)
    if not recipients:
        return 0
    client = service_order.client
    scale = service_order.scale
    signature = 'Sim' if service_order.signature else 'Não'
    subject = f'O.S. {service_order.display_number} assinada — {client.name}'
    body = (
        f'Ordem de Serviço {service_order.display_number} foi assinada.\n\n'
        f'Cliente: {client.name} ({client.document})\n'
        f'Balança: {scale.brand} / {scale.model} — Série {scale.serie}\n'
        f'Data do serviço: {service_order.date:%d/%m/%Y %H:%M}\n'
        f'Assinatura coletada: {signature}\n'
        f'Empresa: {tenant.name}\n'
    )
    return _send(subject, body, recipients)


def send_invite_email(user, invite_url: str) -> int:
    """Envia o convite para o novo usuário definir a senha (expira em 72h)."""
    subject = 'Convite para o Aferix'
    body = (
        f'Olá!\n\n'
        f'Você foi convidado para o Aferix ({user.tenant.name if user.tenant else "Aferix"}).\n'
        f'Email: {user.email}\n\n'
        f'Acesse o link abaixo para criar sua senha (válido por 72 horas):\n'
        f'{invite_url}\n\n'
        f'Se você não esperava este convite, ignore este e-mail.'
    )
    return _send(subject, body, [user.email])


def notify_plan_limit_hit(tenant, resource: str) -> int:
    """Avisa ADMINs sobre bloqueio de limite; no máx. 1 e-mail por dia/recurso."""
    if tenant is None:
        return 0
    key = f'plan-limit-email:{tenant.pk}:{resource}'
    if cache.get(key):
        return 0
    cache.set(key, 1, PLAN_LIMIT_EMAIL_TTL_SECONDS)
    recipients = admin_recipients(tenant)
    if not recipients:
        return 0
    label = RESOURCE_LABELS.get(resource, resource)
    subject = f'Aferix — limite de {label} atingido ({tenant.name})'
    body = (
        f'O limite de {label} do plano atual foi atingido.\n\n'
        f'Novas criações/uso ficam bloqueadas até atualizar o plano.\n'
        f'Refira à tela "Plano e faturamento" para mais detalhes.\n'
    )
    return _send(subject, body, recipients)
