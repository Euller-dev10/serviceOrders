"""Transições de selo e numeração de O.S. com lock (select_for_update)."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from service_order.models import (
    EccentricityTest,
    FidelityTest,
    ServiceOrder,
    Stamp,
    StampDelivery,
    TechnicalReport,
    WeighingTest,
)
from tenants.models import Tenant


def next_os_number(tenant: Tenant) -> int:
    """Próximo número sequencial por tenant, com lock na linha do tenant."""
    if tenant is None:
        raise ValidationError('Tenant obrigatório para numerar O.S.')

    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=tenant.pk)
        last = (
            ServiceOrder.objects.filter(tenant=tenant)
            .aggregate(m=Max('number'))['m']
            or 0
        )
        return last + 1


def next_technical_report_number(tenant: Tenant) -> int:
    """Próximo número de relatório técnico independente da O.S."""
    if tenant is None:
        raise ValidationError('Tenant obrigatório para numerar relatório técnico.')

    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=tenant.pk)
        last = (
            TechnicalReport.objects.filter(tenant=tenant)
            .aggregate(m=Max('number'))['m']
            or 0
        )
        return last + 1


def distribute_stamp(*, stamp: Stamp, user, tenant) -> StampDelivery:
    """Stamp AVAILABLE → DISTRIBUTED + cria StampDelivery AVAILABLE."""
    with transaction.atomic():
        locked = Stamp.objects.select_for_update().get(pk=stamp.pk)
        if locked.tenant_id != tenant.pk:
            raise ValidationError('Selo de outro tenant.')
        if locked.status != 'AVAILABLE':
            raise ValidationError('Selo não está disponível para distribuição.')
        locked.status = 'DISTRIBUTED'
        locked.save(update_fields=['status'])
        return StampDelivery.objects.create(
            tenant=tenant,
            number=locked,
            user=user,
            status='AVAILABLE',
        )


def consume_stamp_for_os(*, delivery_id, service_order: ServiceOrder) -> StampDelivery:
    """Delivery AVAILABLE → USED em transação com lock (consumo único)."""
    with transaction.atomic():
        delivery = (
            StampDelivery.objects.select_for_update()
            .select_related('number')
            .get(pk=delivery_id)
        )
        if delivery.tenant_id != service_order.tenant_id:
            raise ValidationError('Selo de outro tenant.')
        if delivery.status != 'AVAILABLE':
            raise ValidationError('Selo indisponível para esta O.S.')

        stamp = Stamp.objects.select_for_update().get(pk=delivery.number_id)
        if stamp.status != 'DISTRIBUTED':
            raise ValidationError('Selo não está com técnico (estado inválido).')

        delivery.status = 'USED'
        delivery.save(update_fields=['status'])

        service_order.stamp = delivery
        service_order.save(update_fields=['stamp'])
        return delivery


def damage_delivery(*, delivery_id, tenant) -> StampDelivery:
    """Delivery AVAILABLE → DAMAGED; Stamp → DAMAGED."""
    with transaction.atomic():
        delivery = (
            StampDelivery.objects.select_for_update()
            .select_related('number')
            .get(pk=delivery_id)
        )
        if delivery.tenant_id != tenant.pk:
            raise ValidationError('Selo de outro tenant.')
        if delivery.status != 'AVAILABLE':
            raise ValidationError('Apenas selos com técnico podem ser danificados.')

        stamp = Stamp.objects.select_for_update().get(pk=delivery.number_id)
        delivery.status = 'DAMAGED'
        delivery.save(update_fields=['status'])
        stamp.status = 'DAMAGED'
        stamp.save(update_fields=['status'])
        return delivery


def delete_service_order(*, service_order: ServiceOrder, tenant) -> None:
    """Exclui O.S. do tenant e devolve selo USED ao técnico."""
    with transaction.atomic():
        locked = (
            ServiceOrder.objects.select_for_update()
            .select_related('stamp', 'stamp__number')
            .get(pk=service_order.pk)
        )
        if locked.tenant_id != tenant.pk:
            raise ValidationError('O.S. de outro tenant.')
        delivery = locked.stamp
        if delivery is not None and delivery.status == 'USED':
            delivery.status = 'AVAILABLE'
            delivery.save(update_fields=['status'])
            stamp = Stamp.objects.select_for_update().get(pk=delivery.number_id)
            stamp.status = 'DISTRIBUTED'
            stamp.save(update_fields=['status'])
            locked.delete()


def ensure_technical_report_rows(report: TechnicalReport) -> None:
    for model, total in ((FidelityTest, 3), (EccentricityTest, 6), (WeighingTest, 22)):
        for sequence in range(1, total + 1):
            model.objects.get_or_create(report=report, sequence=sequence)


def snapshot_technical_report(report: TechnicalReport) -> TechnicalReport:
    order = report.service_order
    scale = order.scale
    report.technician_name = (
        order.user.get_full_name() or order.user.email
        if order.user else ''
    )
    report.scale_type_snapshot = scale.scale_type
    report.minimum_capacity_snapshot_kg = scale.minimum_capacity_kg
    report.metrological_class_snapshot = scale.metrological_class or ''
    report.capacity_snapshot = scale.capacity or ''
    report.division_snapshot = scale.division or ''
    report.stamp_applied_snapshot = str(order.stamp.number.number) if order.stamp else ''
    report.stamp_retired_snapshot = order.stamp_retired or ''
    return report


def complete_technical_report(report: TechnicalReport) -> TechnicalReport:
    report = snapshot_technical_report(report)
    report.status = TechnicalReport.STATUS_COMPLETED
    report.completed_at = timezone.now()
    report.canceled_at = None
    report.canceled_reason = ''
    report.save()
    return report


def cancel_technical_report(report: TechnicalReport, reason: str) -> TechnicalReport:
    if not reason.strip():
        raise ValidationError('Informe o motivo do cancelamento.')
    report.status = TechnicalReport.STATUS_CANCELED
    report.canceled_at = timezone.now()
    report.canceled_reason = reason.strip()
    report.save(update_fields=['status', 'canceled_at', 'canceled_reason', 'updated_at'])
    return report
