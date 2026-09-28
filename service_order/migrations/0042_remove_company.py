from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('service_order', '0041_serviceorder_status'),
    ]

    operations = [
        migrations.DeleteModel(name='Company'),
    ]
