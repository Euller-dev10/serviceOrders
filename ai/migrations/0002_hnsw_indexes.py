from django.db import migrations


def create_hnsw_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
        columns = {
            'ai_sourcedocument': 'embedding',
            'ai_semanticcache': 'question_embedding',
        }
        for table, column in columns.items():
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS {table}_{column}_hnsw_idx '
                f'ON {table} USING hnsw ({column} vector_cosine_ops)'
            )


def drop_hnsw_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        columns = {
            'ai_sourcedocument': 'embedding',
            'ai_semanticcache': 'question_embedding',
        }
        for table, column in columns.items():
            cursor.execute(f'DROP INDEX IF EXISTS {table}_{column}_hnsw_idx')


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_hnsw_indexes, drop_hnsw_indexes),
    ]
