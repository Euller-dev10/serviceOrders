from django.db import migrations
from django.db import models


def create_default_tenant_and_assign(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Client = apps.get_model('service_order', 'Client')
    Unit = apps.get_model('service_order', 'Unit')
    Scale = apps.get_model('service_order', 'Scale')

    tenant = Tenant.objects.filter(document='00000000000000').first()
    if tenant is None:
        tenant = Tenant.objects.create(
            name='Empresa Padrão (backfill)',
            document='00000000000000',
            status='ACTIVE',
        )

    Client.objects.filter(tenant__isnull=True).update(tenant=tenant)
    Unit.objects.filter(tenant__isnull=True).update(tenant=tenant)
    Scale.objects.filter(tenant__isnull=True).update(tenant=tenant)


def unset_tenant(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('service_order', '0037_normalize_stamp_statuses'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='clients',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='client',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='unit',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='units',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='unit',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='unit',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='scale',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='scales',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='scale',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='scale',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(create_default_tenant_and_assign, unset_tenant),
        migrations.AlterField(
            model_name='client',
            name='tenant',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='clients',
                to='tenants.tenant',
            ),
        ),
        migrations.AlterField(
            model_name='unit',
            name='tenant',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='units',
                to='tenants.tenant',
            ),
        ),
        migrations.AlterField(
            model_name='scale',
            name='tenant',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='scales',
                to='tenants.tenant',
            ),
        ),
        migrations.AddConstraint(
            model_name='client',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'document'), name='uniq_client_tenant_document'
            ),
        ),
        migrations.AddConstraint(
            model_name='unit',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'name'), name='uniq_unit_tenant_name'
            ),
        ),
        migrations.AddConstraint(
            model_name='scale',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'client', 'serie'), name='uniq_scale_serial_per_client'
            ),
        ),
        migrations.AddIndex(
            model_name='scale',
            index=models.Index(
                fields=['tenant', 'client'], name='idx_scale_tenant_client'
            ),
        ),
        migrations.AddIndex(
            model_name='scale',
            index=models.Index(
                fields=['tenant', 'serie'], name='idx_scale_tenant_serie'
            ),
        ),
    ]
