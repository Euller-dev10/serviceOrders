from django.db import migrations, models


def create_default_tenant_and_assign(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Stamp = apps.get_model('service_order', 'Stamp')
    StampDelivery = apps.get_model('service_order', 'StampDelivery')
    ServiceOrder = apps.get_model('service_order', 'ServiceOrder')

    tenant = Tenant.objects.filter(document='00000000000000').first()
    if tenant is None:
        tenant = Tenant.objects.create(
            name='Empresa Padrão (backfill)',
            document='00000000000000',
            status='ACTIVE',
        )

    Stamp.objects.filter(tenant__isnull=True).update(tenant=tenant)
    StampDelivery.objects.filter(tenant__isnull=True).update(tenant=tenant)
    ServiceOrder.objects.filter(tenant__isnull=True).update(tenant=tenant)


def unset_tenant(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('service_order', '0038_tenant_client_scale_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='stamp',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='stamps',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='stamp',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='stamp',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='stampdelivery',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='stamp_deliveries',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='stampdelivery',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='stampdelivery',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='service_orders',
                to='tenants.tenant',
            ),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='number',
            field=models.PositiveIntegerField(
                blank=True, db_index=True, null=True, verbose_name='Número sequencial'
            ),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(create_default_tenant_and_assign, unset_tenant),
        migrations.AlterField(
            model_name='stamp',
            name='tenant',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='stamps',
                to='tenants.tenant',
            ),
        ),
        migrations.AlterField(
            model_name='stampdelivery',
            name='tenant',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='stamp_deliveries',
                to='tenants.tenant',
            ),
        ),
        migrations.AddConstraint(
            model_name='stamp',
            constraint=models.UniqueConstraint(
                fields=('tenant', 'number'), name='uniq_stamp_tenant_number'
            ),
        ),
        migrations.AddConstraint(
            model_name='serviceorder',
            constraint=models.UniqueConstraint(
                condition=models.Q(number__isnull=False),
                fields=('tenant', 'number'),
                name='uniq_os_number_per_tenant',
            ),
        ),
        migrations.AddIndex(
            model_name='serviceorder',
            index=models.Index(
                fields=['tenant', '-date'], name='idx_os_tenant_date'
            ),
        ),
        migrations.AddIndex(
            model_name='serviceorder',
            index=models.Index(
                fields=['tenant', 'user'], name='idx_os_tenant_user'
            ),
        ),
        migrations.AddIndex(
            model_name='serviceorder',
            index=models.Index(
                fields=['tenant', 'client'], name='idx_os_tenant_client'
            ),
        ),
    ]
