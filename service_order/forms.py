from django import forms
from django_select2 import forms as s2forms
from django.forms import inlineformset_factory
from service_order.models import (
    Client,
    EccentricityTest,
    FidelityTest,
    Part,
    Scale,
    ServiceOrder,
    StampDelivery,
    TechnicalReport,
    TimeService,
    WeighingTest,
)

class NewClientModelForm(forms.ModelForm):

    class Meta:
        model = Client
        fields = '__all__'
        exclude = ('tenant', 'created_at', 'updated_at')

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if self.tenant is None and self.instance and self.instance.pk:
            self.tenant = getattr(self.instance, 'tenant', None)

    def clean_document(self):
        document = self.cleaned_data.get('document')
        tenant = self.tenant

        cnpj = Client.objects.filter(document=document)
        if tenant is not None:
            cnpj = cnpj.filter(tenant=tenant)

        if self.instance and self.instance.pk:
            cnpj = cnpj.exclude(pk=self.instance.pk)

        if cnpj.exists():
            self.add_error('document', 'Esse cliente já possui cadastro em nossa base de dados !')
        return document


class NewScaleModelForm(forms.ModelForm):

    class Meta:
        model = Scale
        fields = '__all__'
        exclude = ('tenant', 'created_at', 'updated_at')
        widgets = { 'client':s2forms.ModelSelect2Widget(model=Client, search_fields=['name__icontains', 'document__icontains'], attrs={'data-placeholder':'Razão Social ou CNPJ.....', 'style':'width: 100%;'})}

    def clean(self):

        cleaned_data = super().clean()

        serie = self.cleaned_data.get('serie')
        client = self.cleaned_data.get('client')


        if serie and client:
            scale = Scale.objects.filter(serie=serie, client=client)
            if self.instance and self.instance.pk:
                scale = scale.exclude(pk=self.instance.pk)

            if scale.exists():
                self.add_error('serie', 'Esse número de série já possui cadastro para esse cliente !')

        if self.instance and self.instance.pk and self.instance.scale_type != cleaned_data.get('scale_type'):
            if self.instance.scale_os.filter(
                technical_report__status=TechnicalReport.STATUS_COMPLETED,
            ).exists():
                self.add_error(
                    'scale_type',
                    'Não é possível alterar o tipo de balança com relatório concluído.',
                )

        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Existing equipment records predate the classification field.
        self.fields['scale_type'].required = False


class ServiceOrderForm(forms.ModelForm):

    class Meta:
        model = ServiceOrder
        fields = [
            'service1', 'service2', 'service3', 'service4', 
            'service5', 'service6', 'service7', 'service8', 
            'observation', 'verified', 'new_instalation', 'stamp', 'stamp_retired',
            'signature', 'client_signer_name', 'host', 'food'
        ]

    def __init__(self, *args, **kwargs):
        # Remove o parâmetro customizado 'tecnico' antes de chamar o super
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Adiciona estilização do Bootstrap ao select do selo
        if 'stamp' in self.fields:
            self.fields['stamp'].widget.attrs.update({'class': 'form-select form-select-sm'})
            self.fields['stamp'].empty_label = "Selecione um selo disponível..."
    
        # Filtra os selos se for uma edição (com instância salva)
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            user = self.instance.user
            if user:
                self.fields['stamp'].queryset = StampDelivery.objects.filter(user=user, status='AVAILABLE')
        # Filtra os selos se for uma nova criação e o técnico foi passado
        elif user:
            self.fields['stamp'].queryset = StampDelivery.objects.filter(user=user, status='AVAILABLE')


class TechnicalReportForm(forms.ModelForm):
    action = forms.CharField(required=False, widget=forms.HiddenInput())
    class Meta:
        model = TechnicalReport
        exclude = (
            'service_order', 'tenant', 'number', 'owner_code', 'created_at', 'updated_at', 'status',
            'completed_at', 'canceled_at', 'canceled_reason',
            'scale_type_snapshot', 'minimum_capacity_snapshot_kg',
            'metrological_class_snapshot', 'capacity_snapshot', 'division_snapshot',
            'stamp_applied_snapshot', 'stamp_retired_snapshot',
            'technician_name',
        )
        widgets = {
            'truck_plate_snapshot': forms.TextInput(attrs={'maxlength': 20}),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, require_signature=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_signature = require_signature

    def clean(self):
        return super().clean()

class TechnicalMeasurementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('load_kg', 'indication_kg', 'ema_kg'):
            self.fields[name].localize = True
            self.fields[name].widget.is_localized = True
            self.fields[name].widget.input_type = 'text'
            self.fields[name].widget.attrs.update({'inputmode': 'decimal'})


def _technical_formset(model, fields, extra):
    return inlineformset_factory(
        TechnicalReport,
        model,
        form=TechnicalMeasurementForm,
        fields=fields,
        extra=extra,
        can_delete=False,
    )


FidelityTestFormset = _technical_formset(
    FidelityTest, ['sequence', 'load_kg', 'indication_kg', 'ema_kg'], 3
)
EccentricityTestFormset = _technical_formset(
    EccentricityTest, ['sequence', 'load_kg', 'indication_kg', 'ema_kg'], 6
)
WeighingTestFormset = _technical_formset(
    WeighingTest, ['sequence', 'load_kg', 'indication_kg', 'ema_kg'], 22
)


PartFormset = inlineformset_factory(ServiceOrder, Part, fields=['code', 'amount', 'serie', 'description', 'base'], extra=0, can_delete=True)

TimeFormset = inlineformset_factory(ServiceOrder, TimeService, fields='__all__', extra=0, can_delete=True)

