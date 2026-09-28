"""Auditoria de ações críticas sem registrar PII integral desnecessária."""

from core.models import AuditLog


def mask_document(value):
    digits = ''.join(char for char in str(value or '') if char.isdigit())
    if len(digits) <= 4:
        return '****'
    return f'***{digits[-4:]}'


def record_audit(*, tenant, action, object_type, object_id='', actor=None,
                 metadata=None, request=None):
    if tenant is None:
        return None
    metadata = metadata or {}
    ip_address = None
    user_agent = ''
    if request is not None:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ip_address = (forwarded.split(',')[0].strip() if forwarded
                      else request.META.get('REMOTE_ADDR'))
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    return AuditLog.objects.create(
        tenant=tenant,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        action=action,
        object_type=object_type,
        object_id=str(object_id or ''),
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )
