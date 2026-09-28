from django.db import models

from core.models import get_current_tenant


class TenantManager(models.Manager):
    """Filtra automaticamente pelo tenant do request (contextvar)."""

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        return qs
