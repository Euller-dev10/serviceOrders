from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('service_order', '0046_technicalreport_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='technicalreport',
            name='eccentricity_applied_load_kg',
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=12,
                null=True,
                verbose_name='Carga aplicada no ensaio de excentricidade (kg)',
            ),
        ),
    ]
