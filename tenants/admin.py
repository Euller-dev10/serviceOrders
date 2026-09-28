from django.contrib import admin

from tenants.models import Plan, Subscription, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'document', 'city', 'state', 'status', 'ipem_register')
    search_fields = ('name', 'document', 'city')
    list_filter = ('status',)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'price_monthly_cents',
        'max_technicians',
        'max_service_orders_per_month',
        'is_active',
    )
    list_filter = ('is_active',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'plan', 'status', 'seats_used', 'current_period_end')
    list_filter = ('status',)
