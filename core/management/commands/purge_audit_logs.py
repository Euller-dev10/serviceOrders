from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AuditLog


class Command(BaseCommand):
    help = 'Remove logs de auditoria mais antigos que AUDIT_LOG_RETENTION_DAYS.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=None)

    def handle(self, *args, **options):
        days = options['days'] or settings.AUDIT_LOG_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'{deleted} registros removidos; retenção={days} dias.'))
