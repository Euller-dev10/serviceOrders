"""Expõe banner de limite de plano (soft-block) no template base."""

from tenants.services import usage_summary


def plan_limits(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    if user.is_superuser:
        return {}
    tenant = getattr(user, 'tenant', None) or getattr(request, 'tenant', None)
    if tenant is None:
        return {}
    return {'plan_usage': usage_summary(tenant)}
