from __future__ import annotations

from django.conf import settings

from ai.models import AIConfig, ChatSession


def resolve_ai_config(
    session: ChatSession | None = None,
    tenant=None,
    user=None,
) -> dict:
    """Ordem de resolução: override da sessão → AIConfig do tenant → global → settings.

    Retorna dict com chaves: provider, model_name, source.
    """
    if session is not None:
        if session.model_provider:
            return {
                'provider': session.model_provider,
                'model_name': session.model_name or None,
                'source': 'session',
            }
        if session.tenant_id and tenant is None:
            tenant = session.tenant
        if tenant is None and user is not None and getattr(user, 'tenant_id', None):
            tenant = user.tenant

    if tenant is not None:
        config = (
            AIConfig.objects.filter(tenant=tenant, is_active=True)
            .order_by('-updated_at')
            .first()
        )
        if config is not None:
            return {
                'provider': config.provider,
                'model_name': config.model_name or None,
                'source': 'tenant',
            }

    global_config = (
        AIConfig.objects.filter(tenant__isnull=True, is_active=True)
        .order_by('-updated_at')
        .first()
    )
    if global_config is not None:
        return {
            'provider': global_config.provider,
            'model_name': global_config.model_name or None,
            'source': 'global',
        }

    return {
        'provider': getattr(settings, 'AI_DEFAULT_PROVIDER', 'mock'),
        'model_name': getattr(settings, 'AI_DEFAULT_MODEL', '') or None,
        'source': 'settings',
    }
