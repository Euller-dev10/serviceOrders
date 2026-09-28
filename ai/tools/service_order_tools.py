"""Tools de domínio — tenant_id SEMPRE injetado pelo runtime (nunca pelo LLM)."""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count

from service_order.models import Client, Scale, ServiceOrder

MAX_LIMIT = 50

SERVICE_LABELS = {
    'service1': 'Manutenção corretiva',
    'service2': 'Manutenção preventiva',
    'service3': 'Certificação com pesos padrão',
    'service4': 'Ajustes com pesos padrão',
    'service5': 'Certificado de conformidade',
    'service6': 'Reparo em plataforma/estrutura metálica',
    'service7': 'Reparo em dispositivo eletroeletrônico',
    'service8': 'Reparo em comunicação / equipamentos externos',
}


class ToolError(Exception):
    """Erro amigável em pt-BR (sem stack trace para o LLM)."""


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return 20
    return max(1, min(int(limit), MAX_LIMIT))


def _scope_orders(qs, *, user_id: int | None = None, user_role: str | None = None):
    if user_role == 'TECHNICIAN' and user_id:
        return qs.filter(user_id=user_id)
    return qs


def _serialize_os(os: ServiceOrder) -> dict:
    services = [label for flag, label in SERVICE_LABELS.items() if getattr(os, flag, False)]
    return {
        'pk': os.pk,
        'number': os.number,
        'display_number': os.display_number,
        'client': os.client.name if os.client_id else None,
        'client_document': os.client.document if os.client_id else None,
        'scale': (
            f'{os.scale.brand} {os.scale.serie}' if os.scale_id else None
        ),
        'scale_model': os.scale.model if os.scale_id else None,
        'scale_serial': os.scale.serie if os.scale_id else None,
        'date': os.date.isoformat() if os.date else None,
        'services': services,
        'verified_inmetro': os.verified,
        'observation': os.observation or '',
        'problem': os.observation or '',
        'user': os.user.email if os.user_id else None,
    }


def search_service_orders(
    *,
    tenant_id: int,
    client_cnpj: str | None = None,
    client_name: str | None = None,
    date_from=None,
    date_to=None,
    service_flag: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    user_id: int | None = None,
    user_role: str | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    qs = ServiceOrder.objects.filter(tenant_id=tenant_id).select_related('client', 'scale', 'user')
    qs = _scope_orders(qs, user_id=user_id, user_role=user_role)
    if client_cnpj:
        digits = ''.join(c for c in str(client_cnpj) if c.isdigit())
        if digits:
            qs = qs.filter(client__document__icontains=digits)
    if client_name:
        qs = qs.filter(client__name__icontains=client_name.strip())
    if date_from:
        qs = qs.filter(date__date__gte=date_from)
    if date_to:
        qs = qs.filter(date__date__lte=date_to)
    if service_flag in SERVICE_LABELS:
        qs = qs.filter(**{service_flag: True})
    if verified is not None:
        qs = qs.filter(verified=verified)

    limit = _clamp_limit(limit)
    total = qs.count()
    rows = [_serialize_os(o) for o in qs.order_by('-date')[:limit]]
    return {'total_matching': total, 'returned': len(rows), 'results': rows}


def get_service_order(
    *,
    tenant_id: int,
    number: int | None = None,
    pk: int | None = None,
    user_id: int | None = None,
    user_role: str | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    qs = ServiceOrder.objects.filter(tenant_id=tenant_id).select_related('client', 'scale', 'user')
    qs = _scope_orders(qs, user_id=user_id, user_role=user_role)
    os_obj = None
    if number is not None:
        os_obj = qs.filter(number=number).first()
    if os_obj is None and pk is not None:
        os_obj = qs.filter(pk=pk).first()
    if os_obj is None:
        raise ToolError('Ordem de serviço não encontrada nesta empresa.')
    return _serialize_os(os_obj)


def get_client(
    *,
    tenant_id: int,
    document: str | None = None,
    pk: int | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    qs = Client.objects.filter(tenant_id=tenant_id)
    client = None
    if document:
        digits = ''.join(c for c in str(document) if c.isdigit())
        if digits:
            client = qs.filter(document__icontains=digits).first()
    if client is None and pk is not None:
        client = qs.filter(pk=pk).first()
    if client is None:
        raise ToolError('Cliente não encontrado nesta empresa.')
    return {
        'pk': client.pk,
        'name': client.name,
        'document': client.document,
        'city': client.city,
        'uf': client.uf,
        'contact': client.contact,
        'email': client.email,
    }


def list_scale_history(
    *,
    tenant_id: int,
    scale_pk: int | None = None,
    serial_number: str | None = None,
    limit: int = 20,
    user_id: int | None = None,
    user_role: str | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    scale_qs = Scale.objects.filter(tenant_id=tenant_id)
    scale = None
    if serial_number:
        scale = scale_qs.filter(serie__icontains=serial_number).first()
    if scale is None and scale_pk is not None:
        scale = scale_qs.filter(pk=scale_pk).first()
    if scale is None:
        raise ToolError('Balança não encontrada nesta empresa.')

    limit = _clamp_limit(limit)
    qs = (
        ServiceOrder.objects.filter(tenant_id=tenant_id, scale=scale)
        .select_related('client', 'user')
        .order_by('-date')
    )
    qs = _scope_orders(qs, user_id=user_id, user_role=user_role)
    total = qs.count()
    results = [_serialize_os(o) for o in qs[:limit]]
    return {
        'scale': {
            'pk': scale.pk,
            'brand': scale.brand,
            'model': scale.model,
            'serie': scale.serie,
            'capacity': scale.capacity,
        },
        'total_matching': total,
        'returned': len(results),
        'results': results,
    }


def aggregate_service_orders(
    *,
    tenant_id: int,
    date_from=None,
    date_to=None,
    group_by: str = 'service_flag',
    user_id: int | None = None,
    user_role: str | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    qs = ServiceOrder.objects.filter(tenant_id=tenant_id)
    qs = _scope_orders(qs, user_id=user_id, user_role=user_role)
    if date_from:
        qs = qs.filter(date__date__gte=date_from)
    if date_to:
        qs = qs.filter(date__date__lte=date_to)

    total = qs.count()
    buckets: list[dict] = []

    if group_by == 'status':
        # MVP: sem campo status — conta por selo aplicado
        used = qs.filter(stamp__isnull=False).count()
        buckets = [
            {'key': 'with_stamp', 'label': 'Com selo', 'count': used},
            {'key': 'without_stamp', 'label': 'Sem selo', 'count': total - used},
        ]
    elif group_by == 'client':
        rows = (
            qs.values('client_id', 'client__name')
            .annotate(c=Count('id'))
            .order_by('-c')[:50]
        )
        buckets = [
            {'key': r['client_id'], 'label': r['client__name'] or '—', 'count': r['c']}
            for r in rows
        ]
    elif group_by == 'day':
        rows = (
            qs.extra(select={'day': "date(date)"})
            .values('day')
            .annotate(c=Count('id'))
            .order_by('day')[:50]
        )
        buckets = [
            {'key': str(r['day']), 'label': str(r['day']), 'count': r['c']}
            for r in rows
        ]
    else:  # service_flag
        for flag, label in SERVICE_LABELS.items():
            buckets.append({
                'key': flag,
                'label': label,
                'count': qs.filter(**{flag: True}).count(),
            })

    return {'total': total, 'group_by': group_by, 'buckets': buckets}


def draft_service_report(
    *,
    tenant_id: int,
    number: int | None = None,
    pk: int | None = None,
    tone: str = 'tecnico',
    user_id: int | None = None,
    user_role: str | None = None,
    **_ignored,
) -> dict:
    if not tenant_id:
        raise ToolError('Contexto de empresa ausente.')
    qs = ServiceOrder.objects.filter(tenant_id=tenant_id).select_related('client', 'scale', 'user')
    qs = _scope_orders(qs, user_id=user_id, user_role=user_role)
    os_obj = None
    if number is not None:
        os_obj = qs.filter(number=number).first()
    if os_obj is None and pk is not None:
        os_obj = qs.filter(pk=pk).first()
    if os_obj is None:
        raise ToolError('Ordem de serviço não encontrada nesta empresa.')

    services = [label for flag, label in SERVICE_LABELS.items() if getattr(os_obj, flag, False)]
    scale_desc = (
        f'{os_obj.scale.brand} {os_obj.scale.model} (série {os_obj.scale.serie})'
        if os_obj.scale_id
        else '—'
    )
    observation = (os_obj.observation or '').strip()

    if tone == 'cliente':
        draft = (
            f'Serviço realizado em {os_obj.client.name} — balança {scale_desc}. '
            f'Serviços: {", ".join(services) or "—"}.'
        )
        if observation:
            draft += f' Observações: {observation}'
    elif tone == 'resumido':
        draft = (
            f'OS {os_obj.display_number}: {", ".join(services) or "sem serviços marcados"}. '
            f'Equipamento: {scale_desc}.'
        )
    else:
        lines = [
            f'LAUDO TÉCNICO — OS {os_obj.display_number}',
            f'Cliente: {os_obj.client.name} ({os_obj.client.document})',
            f'Equipamento: {scale_desc}',
            f'Data: {os_obj.date.strftime("%d/%m/%Y") if os_obj.date else "—"}',
            f'Serviços executados: {", ".join(services) or "—"}',
            f'Verificado pelo Inmetro: {"sim" if os_obj.verified else "não"}',
        ]
        if observation:
            lines.append(f'Observações: {observation}')
        lines.append(
            'Declaração: os serviços acima foram executados conforme normas aplicáveis.'
        )
        draft = '\n'.join(lines)

    return {
        'os_pk': os_obj.pk,
        'number': os_obj.number,
        'display_number': os_obj.display_number,
        'tone': tone,
        'draft': draft,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }
