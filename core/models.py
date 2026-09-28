from contextvars import ContextVar

from django.db import models

_current_tenant: ContextVar = ContextVar('current_tenant', default=None)


def get_current_tenant():
    return _current_tenant.get()


def set_current_tenant(tenant):
    return _current_tenant.set(tenant)


def reset_current_tenant(token):
    _current_tenant.reset(token)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimeStampedModel):
    from core.managers import TenantManager

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='+',
        db_index=True,
    )
    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        abstract = True


class AuditLog(TenantScopedModel):
    """Registro imutável de ações sensíveis realizadas no tenant."""

    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_DELETE = 'DELETE'
    ACTION_EXPORT = 'EXPORT'
    ACTION_ANONYMIZE = 'ANONYMIZE'
    ACTION_STAMP_DISTRIBUTE = 'STAMP_DISTRIBUTE'
    ACTION_STAMP_DAMAGE = 'STAMP_DAMAGE'
    ACTION_CHOICES = (
        (ACTION_CREATE, 'Criação'),
        (ACTION_UPDATE, 'Atualização'),
        (ACTION_DELETE, 'Exclusão'),
        (ACTION_EXPORT, 'Exportação'),
        (ACTION_ANONYMIZE, 'Anonimização'),
        (ACTION_STAMP_DISTRIBUTE, 'Distribuição de selo'),
        (ACTION_STAMP_DAMAGE, 'Dano em selo'),
    )

    actor = models.ForeignKey(
        'accounts.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', '-created_at'], name='idx_audit_tenant_created'),
            models.Index(fields=['tenant', 'action'], name='idx_audit_tenant_action'),
        ]
