from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'role', 'tenant', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('role', 'is_active', 'is_staff')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Pessoal', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissões', {'fields': ('role', 'tenant', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Convite', {'fields': ('invite_token', 'invite_expires_at')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'role',
                    'tenant',
                    'is_active',
                )
            },
        ),
    )
    filter_horizontal = ('groups', 'user_permissions')
