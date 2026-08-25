from django.contrib import admin
from service_order.models import Client, Unit, Scale, ServiceOrder, Part, Stamp, StampDelivery, TimeService, Company

class ClientAdmin(admin.ModelAdmin):

    list_display = ('name', 'document', 'state_registration', 'address', 'district', 'city', 'uf', 'cep', 'contact', 'email')
    search_fields = ('name', 'document', 'city')


class UnitAdmin(admin.ModelAdmin):

    list_display = ['name']
    search_fields = ['name']


class ScaleAdmin(admin.ModelAdmin):

    list_display = ('brand', 'model', 'serie', 'capacity', 'unit', 'division', 'portaria', 'client')
    search_fields = ('client', 'serie')

class ServiceOrderAdmin(admin.ModelAdmin):

    list_display = ['id', 'client', 'scale', 'service1', 'service2', 'service3', 'service4', 'service5', 'service6', 'service7', 'observation', 'verified', 'date', 'user', 'new_instalation', 'stamp' ]
    search_fields = ['client', 'scale', 'service1', 'service2', 'service3', 'service4', 'service5', 'service6', 'service7', 'part', 'observation', 'verified', 'date', 'user', 'new_instalation', 'stamp' ]


class PartAdmin(admin.ModelAdmin):

    list_display = ['code', 'amount', 'description', 'base', 'service_order']
    search_fields = ['code', 'amount', 'description', 'base', 'service_order']

class StampAdmin(admin.ModelAdmin):
    list_display = ['number']
    search_fields = ['number']

class StampDeliveryAdmin(admin.ModelAdmin):
    list_display = ['number', 'date', 'user']
    search_fields = ['number', 'date', 'user']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Quando o Django for renderizar o campo 'number' (a ForeignKey)
        if db_field.name == "number":
            # Filtra para mostrar apenas os selos que estão DISPONIVEL
            kwargs["queryset"] = db_field.related_model.objects.filter(status='DISPONIVEL')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class TimeServiceAdmin(admin.ModelAdmin):
    list_display = ['day', 'start', 'stop', 'total_hours', 'car', 'truck', 'service_order']
    search_fields = ['day', 'start', 'stop', 'total_hours', 'car', 'truck', 'service_order']

class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'document', 'state_registration', 'address', 'district', 'city', 'uf', 'cep', 'contact', 'email', 'number_register', 'logo']
    search_fields = ['name', 'document', 'city']



admin.site.register(Client, ClientAdmin)
admin.site.register(Unit, UnitAdmin)
admin.site.register(Scale, ScaleAdmin)
admin.site.register(ServiceOrder, ServiceOrderAdmin)
admin.site.register(Part, PartAdmin)
admin.site.register(Stamp, StampAdmin)
admin.site.register(StampDelivery, StampDeliveryAdmin)
admin.site.register(TimeService, TimeServiceAdmin)
admin.site.register(Company, CompanyAdmin)
