from django.contrib import admin

from core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'tenant', 'action', 'object_type', 'object_id', 'actor')
    list_filter = ('action', 'object_type', 'tenant')
    search_fields = ('object_id', 'actor__email', 'tenant__name')
    readonly_fields = (
        'tenant', 'actor', 'action', 'object_type', 'object_id', 'metadata',
        'ip_address', 'user_agent', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
