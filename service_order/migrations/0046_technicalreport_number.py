from django.db import migrations, models


def populate_report_numbers(apps, schema_editor):
    TechnicalReport = apps.get_model('service_order', 'TechnicalReport')
    reports = TechnicalReport.objects.order_by('tenant_id', 'created_at', 'pk')
    counters = {}
    for report in reports:
        number = counters.get(report.tenant_id, 0) + 1
        counters[report.tenant_id] = number
        report.number = number
        report.save(update_fields=['number'])


class Migration(migrations.Migration):
    dependencies = [
        ('service_order', '0045_remove_technicalreport_owner_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='technicalreport',
            name='number',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Número do relatório'),
        ),
        migrations.RunPython(populate_report_numbers, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='technicalreport',
            constraint=models.UniqueConstraint(
                condition=models.Q(number__isnull=False),
                fields=('tenant', 'number'),
                name='uniq_report_number_per_tenant',
            ),
        ),
    ]
