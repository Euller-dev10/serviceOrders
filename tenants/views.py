"""Tela de billing somente leitura (MVP — gateway depois)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from core.permissions import AdminRequiredMixin, TenantRequiredMixin
from tenants.services import billing_context, ensure_subscription


@method_decorator(login_required(login_url='login'), name='dispatch')
class BillingView(AdminRequiredMixin, TenantRequiredMixin, View):
    """Exibe plano, assinatura vigente e uso no ciclo (sem alteração)."""

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, 'tenant', None) or getattr(
            request.user, 'tenant', None
        )
        ensure_subscription(tenant)
        ctx = billing_context(tenant)
        return render(request, 'billing.html', ctx)
