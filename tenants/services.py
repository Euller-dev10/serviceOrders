"""Limites de plano — seed, Subscription vigente, contadores e gate (Sprint 3.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.utils import timezone

from tenants.models import Plan, Subscription, Tenant

PLAN_SEED = [
    {
        'code': 'trial',
        'name': 'Trial 14 dias',
        'price_monthly_cents': 0,
        'max_technicians': 3,
        'max_service_orders_per_month': 30,
        'max_ai_credits_per_month': 50,
        'ai_enabled': True,
        'required_signature': False,
        'is_active': True,
    },
    {
        'code': 'basic',
        'name': 'Básico',
        'price_monthly_cents': 14900,
        'max_technicians': 3,
        'max_service_orders_per_month': 100,
        'max_ai_credits_per_month': 200,
        'ai_enabled': True,
        'required_signature': False,
        'is_active': True,
    },
    {
        'code': 'pro',
        'name': 'Profissional',
        'price_monthly_cents': 34900,
        'max_technicians': 10,
        'max_service_orders_per_month': 500,
        'max_ai_credits_per_month': 1000,
        'ai_enabled': True,
        'required_signature': True,
        'is_active': True,
    },
    {
        'code': 'enterprise',
        'name': 'Enterprise',
        'price_monthly_cents': 0,
        'max_technicians': None,
        'max_service_orders_per_month': None,
        'max_ai_credits_per_month': None,
        'ai_enabled': True,
        'required_signature': True,
        'is_active': True,
    },
]

SUBSCRIPTION_OK_STATUSES = (
    Subscription.STATUS_ACTIVE,
    Subscription.STATUS_TRIALING,
)

RESOURCE_OSES = 'service_orders'
RESOURCE_SEATS = 'seats'
RESOURCE_AI = 'ai_credits'

RESOURCE_LABELS = {
    RESOURCE_OSES: 'Ordens de Serviço/mês',
    RESOURCE_SEATS: 'Assentos',
    RESOURCE_AI: 'Créditos IA/mês',
}


def seed_plans() -> list[Plan]:
    """Cria ou atualiza os 4 planos baseline (§12.2). Idempotente."""
    plans = []
    for payload in PLAN_SEED:
        code = payload['code']
        plan, _created = Plan.objects.update_or_create(
            code=code,
            defaults=payload,
        )
        plans.append(plan)
    return plans


def get_or_create_trial_subscription(tenant: Tenant) -> Subscription:
    """Subscription 1:1 no trial de 14 dias se ainda não existir."""
    plan, _ = Plan.objects.get_or_create(
        code='trial',
        defaults=PLAN_SEED[0],
    )
    now = timezone.now()
    sub, _created = Subscription.objects.get_or_create(
        tenant=tenant,
        defaults={
            'plan': plan,
            'status': Subscription.STATUS_TRIALING,
            'current_period_start': now,
            'current_period_end': now + timedelta(days=14),
            'seats_used': 0,
        },
    )
    return sub


def get_subscription(tenant: Tenant | None) -> Subscription | None:
    """Subscription vigente (ativa/trialing e período aberto), se houver."""
    if tenant is None:
        return None
    try:
        sub = tenant.subscription
    except Subscription.DoesNotExist:
        return None
    if sub.status not in SUBSCRIPTION_OK_STATUSES:
        return None
    now = timezone.now()
    if sub.current_period_end and sub.current_period_end < now:
        return None
    return sub


def get_plan(tenant: Tenant | None) -> Plan | None:
    sub = get_subscription(tenant)
    if sub is None:
        return None
    return sub.plan


def _period_bounds(sub: Subscription | None) -> tuple:
    """Início/fim do ciclo de contagem; fallback = mês corrente (timezone local)."""
    now = timezone.now()
    if sub and sub.current_period_start:
        start = sub.current_period_start
        if sub.current_period_end:
            end = sub.current_period_end
        else:
            end = start + timedelta(days=30)
        if start <= now <= end:
            return start, end
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_start = start.replace(year=start.year + 1, month=1)
    else:
        next_start = start.replace(month=start.month + 1)
    return start, next_start - timezone.timedelta(microseconds=1)


def count_service_orders(tenant: Tenant, sub: Subscription | None = None) -> int:
    from service_order.models import ServiceOrder

    start, end = _period_bounds(sub if sub is not None else get_subscription(tenant))
    return ServiceOrder.objects.filter(
        tenant=tenant,
        date__gte=start,
        date__lte=end,
    ).count()


def count_seats(tenant: Tenant) -> int:
    from accounts.models import User

    return User.objects.filter(tenant=tenant).exclude(
        Q(is_superuser=True) | Q(is_active=False)
    ).count()


def count_active_admins(tenant: Tenant) -> int:
    from accounts.models import User

    return User.objects.filter(
        tenant=tenant, role='ADMIN', is_active=True
    ).count()


def count_active_users(tenant: Tenant) -> int:
    from accounts.models import User

    return User.objects.filter(tenant=tenant, is_active=True).exclude(
        is_superuser=True
    ).count()


def count_ai_credits(tenant: Tenant, sub: Subscription | None = None) -> int:
    """1 crédito ≈ 1 turno de chat (mensagem do usuário no período)."""
    from ai.models import ChatMessage

    start, end = _period_bounds(sub if sub is not None else get_subscription(tenant))
    return ChatMessage.objects.filter(
        tenant=tenant,
        role='user',
        created_at__gte=start,
        created_at__lte=end,
    ).count()


def _limit_of(plan: Plan | None, resource: str) -> int | None:
    if plan is None:
        return None
    if resource == RESOURCE_OSES:
        return plan.max_service_orders_per_month
    if resource == RESOURCE_SEATS:
        return plan.max_technicians
    if resource == RESOURCE_AI:
        return plan.max_ai_credits_per_month
    raise ValueError(f'Recurso desconhecido: {resource}')


@dataclass(frozen=True)
class LimitStatus:
    resource: str
    used: int
    limit: int | None
    plan_code: str | None
    over_limit: bool
    near_limit: bool
    hard_block: bool
    feature_disabled: bool = False
    subscription_inactive: bool = False

    @property
    def allowed(self) -> bool:
        return not self.hard_block


def check_plan_limit(
    tenant: Tenant | None,
    resource: str,
    *,
    hard: bool = False,
) -> LimitStatus:
    """Avalia uso vs. limite. `hard=True` exige bloqueio de criação (Enterprise/over)."""
    if tenant is None:
        return LimitStatus(resource, 0, None, None, False, False, False)

    # Tenants antigos ou recém-criados recebem o trial automaticamente na
    # primeira avaliação de limites, sem depender de uma visita à tela de billing.
    ensure_subscription(tenant)
    sub = get_subscription(tenant)
    plan = sub.plan if sub else None
    limit = _limit_of(plan, resource)

    if resource == RESOURCE_OSES:
        used = count_service_orders(tenant, sub)
    elif resource == RESOURCE_SEATS:
        used = count_seats(tenant)
    elif resource == RESOURCE_AI:
        used = count_ai_credits(tenant, sub)
    else:
        raise ValueError(f'Recurso desconhecido: {resource}')

    over = limit is not None and used >= limit
    near = limit is not None and not over and used >= int(limit * 0.8)
    # Enterprise (limit=None) nunca hard-bloqueia por contagem.
    # Soft: banner quando perto/excedeu; hard: bloqueia criação ao exceder.
    subscription_inactive = sub is None
    feature_disabled = resource == RESOURCE_AI and plan is not None and not plan.ai_enabled
    block = hard and (over or subscription_inactive or feature_disabled)
    return LimitStatus(
        resource=resource,
        used=used,
        limit=limit,
        plan_code=plan.code if plan else None,
        over_limit=over,
        near_limit=near,
        hard_block=block,
        feature_disabled=feature_disabled,
        subscription_inactive=subscription_inactive,
    )


def usage_summary(tenant: Tenant | None) -> dict:
    """Uso no ciclo corrente para billing e banner."""
    if tenant is None:
        return {
            'plan': None,
            'subscription': None,
            'os': {'used': 0, 'limit': None, 'over': False},
            'seats': {'used': 0, 'limit': None, 'over': False},
            'ai': {'used': 0, 'limit': None, 'over': False},
            'over_limit': False,
            'any_warning': False,
        }
    ensure_subscription(tenant)
    sub = get_subscription(tenant)
    os_st = check_plan_limit(tenant, RESOURCE_OSES, hard=False)
    seat_st = check_plan_limit(tenant, RESOURCE_SEATS, hard=False)
    ai_st = check_plan_limit(tenant, RESOURCE_AI, hard=False)
    return {
        'plan': sub.plan if sub else None,
        'subscription': sub,
        'os': {'used': os_st.used, 'limit': os_st.limit, 'over': os_st.over_limit},
        'seats': {
            'used': seat_st.used,
            'limit': seat_st.limit,
            'over': seat_st.over_limit,
        },
        'ai': {'used': ai_st.used, 'limit': ai_st.limit, 'over': ai_st.over_limit},
        'over_limit': os_st.over_limit or seat_st.over_limit or ai_st.over_limit,
        'any_warning': (
            os_st.over_limit or os_st.near_limit
            or seat_st.over_limit or seat_st.near_limit
            or ai_st.over_limit or ai_st.near_limit
        ),
    }


def ensure_subscription(tenant: Tenant | None) -> Subscription | None:
    if tenant is None:
        return None
    sub = get_subscription(tenant)
    if sub is None:
        try:
            return tenant.subscription
        except Subscription.DoesNotExist:
            return get_or_create_trial_subscription(tenant)
    return sub


def enforce_limit_or_deny(
    request,
    tenant: Tenant | None,
    resource: str,
    *,
    redirect_name: str = 'home',
) -> bool:
    """Retorna True se a ação de criação é permitida; senão nega (hard block)."""
    status = check_plan_limit(tenant, resource, hard=True)
    if status.allowed:
        return True
    label = RESOURCE_LABELS.get(resource, resource)
    messages.error(
        request,
        _limit_error_message(status, label),
    )
    from core.emails import notify_plan_limit_hit

    notify_plan_limit_hit(tenant, resource)
    return False


def plan_limit_decorator(resource: str, redirect_name: str = 'home'):
    """Decorator de view: hard block quando o recurso estiver no limite."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            tenant = getattr(request, 'tenant', None)
            if tenant is None and getattr(request, 'user', None):
                tenant = getattr(request.user, 'tenant', None)
            status = check_plan_limit(tenant, resource, hard=True)
            if not status.allowed:
                label = RESOURCE_LABELS.get(resource, resource)
                messages.error(request, _limit_error_message(status, label))
                from core.emails import notify_plan_limit_hit

                notify_plan_limit_hit(tenant, resource)
                return redirect(redirect_name)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def seat_limit_reached(tenant) -> bool:
    """True se criar novo assento excederia o limite do plano."""
    status = check_plan_limit(tenant, RESOURCE_SEATS, hard=True)
    return not status.allowed


def period_bounds(tenant):
    """(início, fim) do ciclo de contagem (assinatura vigente ou mês corrente)."""
    return _period_bounds(get_subscription(tenant))


def _limit_error_message(status: LimitStatus, label: str) -> str:
    if status.subscription_inactive:
        return 'A assinatura da empresa não está ativa. Consulte o faturamento para regularizar.'
    if status.feature_disabled:
        return 'O Assistente IA não está habilitado no plano atual.'
    return (
        f'Limite de {label} atingido no plano '
        f'{status.plan_code}. Consulte o faturamento para atualizar o plano.'
    )


def billing_context(tenant: Tenant | None) -> dict:
    """Dados somente leitura da tela de billing (MVP sem gateway)."""
    summary = usage_summary(tenant)
    sub = ensure_subscription(tenant)
    plan = sub.plan if sub else None
    plans = Plan.objects.filter(is_active=True).order_by('price_monthly_cents')

    def price_for(item):
        if item.code == 'enterprise':
            return 'Sob consulta'
        amount = item.price_monthly_cents / 100
        return f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    return {
        'subscription': sub,
        'plan': plan,
        'usage': summary,
        'period_start': sub.current_period_start if sub else None,
        'period_end': sub.current_period_end if sub else None,
        'plans': [
            {
                'plan': item,
                'price_display': price_for(item),
                'seats_display': item.max_technicians if item.max_technicians is not None else 'Ilimitado',
                'os_display': (
                    item.max_service_orders_per_month
                    if item.max_service_orders_per_month is not None else 'Ilimitado'
                ),
                'ai_display': (
                    item.max_ai_credits_per_month
                    if item.max_ai_credits_per_month is not None else 'Ilimitado'
                ),
            }
            for item in plans
        ],
        'seats_limit_display': (
            'Ilimitado' if plan and plan.max_technicians is None
            else (plan.max_technicians if plan else '—')
        ),
        'os_limit_display': (
            'Ilimitado' if plan and plan.max_service_orders_per_month is None
            else (plan.max_service_orders_per_month if plan else '—')
        ),
        'ai_limit_display': (
            'Ilimitado' if plan and plan.max_ai_credits_per_month is None
            else (plan.max_ai_credits_per_month if plan else '—')
        ),
        'price_display': (
            'Sob consulta'
            if plan and plan.code == 'enterprise'
            else (
                f'R$ {plan.price_monthly_cents / 100:.2f}'.replace('.', ',')
                if plan else '—'
            )
        ),
    }
