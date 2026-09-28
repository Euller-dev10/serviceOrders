"""Operações LGPD sobre dados de clientes finais."""

import hashlib
import uuid

from django.db import transaction

from core.audit import record_audit
from core.models import AuditLog


def export_client_data(*, client, actor=None, request=None):
    orders = client.client_os.select_related('scale', 'user').order_by('date')
    payload = {
        'client': {
            'id': client.pk,
            'name': client.name,
            'document': client.document,
            'state_registration': client.state_registration or '',
            'address': client.address or '',
            'district': client.district or '',
            'city': client.city or '',
            'uf': client.uf or '',
            'cep': client.cep or '',
            'contact': client.contact or '',
            'email': client.email or '',
        },
        'service_orders': [
            {
                'id': order.pk,
                'number': order.display_number,
                'date': order.date.isoformat() if order.date else None,
                'status': order.status,
                'scale': order.scale.serie,
                'signature': order.signature or '',
            }
            for order in orders
        ],
    }
    record_audit(
        tenant=client.tenant,
        actor=actor,
        action=AuditLog.ACTION_EXPORT,
        object_type='Client',
        object_id=client.pk,
        metadata={'purpose': 'LGPD_DATA_SUBJECT_EXPORT'},
        request=request,
    )
    return payload


@transaction.atomic
def anonymize_client(*, client, actor=None, request=None):
    old_document = client.document
    anonymized_document = 'ANON-' + hashlib.sha256(
        f'{client.tenant_id}:{client.pk}:{uuid.uuid4()}'.encode()
    ).hexdigest()[:24]
    client.name = f'Cliente anonimizado {client.pk}'
    client.document = anonymized_document
    client.state_registration = ''
    client.address = ''
    client.district = ''
    client.city = ''
    client.uf = ''
    client.cep = ''
    client.contact = ''
    client.email = ''
    client.save()
    client.client_os.update(signature='', observation='')
    record_audit(
        tenant=client.tenant,
        actor=actor,
        action=AuditLog.ACTION_ANONYMIZE,
        object_type='Client',
        object_id=client.pk,
        metadata={
            'purpose': 'LGPD_DATA_SUBJECT_ERASURE',
            'previous_document': hashlib.sha256(str(old_document).encode()).hexdigest(),
        },
        request=request,
    )
    return client
