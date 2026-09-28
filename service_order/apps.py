from django.apps import AppConfig


class ServiceOrderConfig(AppConfig):
    name = 'service_order'

    def ready(self):
        import service_order.signals  # noqa: F401
