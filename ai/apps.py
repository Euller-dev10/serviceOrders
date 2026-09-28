from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai'
    verbose_name = 'IA'

    def ready(self):
        from django.db.backends.signals import connection_created

        from ai import pgvector_compat

        connection_created.connect(pgvector_compat.register_pgvector)
