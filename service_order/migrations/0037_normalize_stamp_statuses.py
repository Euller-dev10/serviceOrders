from django.db import migrations

STAMP_MAP = {
    'DISPONIVEL': 'AVAILABLE',
    'DISTRIBUÍDO': 'DISTRIBUTED',
    'DANIFICADO': 'DAMAGED',
}

DELIVERY_MAP = {
    'DISPONIVEL': 'AVAILABLE',
    'UTILIZADO': 'USED',
    'DANIFICADO': 'DAMAGED',
}


def normalize_statuses(apps, schema_editor):
    Stamp = apps.get_model('service_order', 'Stamp')
    StampDelivery = apps.get_model('service_order', 'StampDelivery')

    for old, new in STAMP_MAP.items():
        Stamp.objects.filter(status=old).update(status=new)
    for old, new in DELIVERY_MAP.items():
        StampDelivery.objects.filter(status=old).update(status=new)


def unnormalize_statuses(apps, schema_editor):
    Stamp = apps.get_model('service_order', 'Stamp')
    StampDelivery = apps.get_model('service_order', 'StampDelivery')

    reverse_stamp = {v: k for k, v in STAMP_MAP.items()}
    reverse_delivery = {v: k for k, v in DELIVERY_MAP.items()}

    for old, new in reverse_stamp.items():
        Stamp.objects.filter(status=old).update(status=new)
    for old, new in reverse_delivery.items():
        StampDelivery.objects.filter(status=old).update(status=new)


class Migration(migrations.Migration):

    dependencies = [
        ('service_order', '0036_alter_stamp_status_alter_stampdelivery_status'),
    ]

    operations = [
        migrations.RunPython(normalize_statuses, unnormalize_statuses),
    ]
