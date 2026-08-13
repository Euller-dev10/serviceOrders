from django import forms
from django_select2 import forms as s2forms
from django.forms import inlineformset_factory
from service_order.models import Client, Scale, ServiceOrder, Part, StampDelivery, TimeService

class NewClientModelForm(forms.ModelForm):

    class Meta:
        model = Client
        fields = '__all__'
    
    def clean_document(self):
        document = self.cleaned_data.get('document')

        cnpj = Client.objects.filter(document=document)

        if self.instance and self.instance.pk:
            cnpj = cnpj.exclude(pk=self.instance.pk)

        if cnpj.exists():
            self.add_error('document', 'Esse cliente já possui cadastro em nossa base de dados !')
        return document


class NewScaleModelForm(forms.ModelForm):

    class Meta:
        model = Scale
        fields = '__all__'
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

        return cleaned_data
    
from django import forms

class ServiceOrderForm(forms.ModelForm):

    class Meta:
        model = ServiceOrder
        fields = [
            'service1', 'service2', 'service3', 'service4', 
            'service5', 'service6', 'service7', 'service8', 
            'observation', 'verified', 'new_instalation', 'stamp',
            'signature', 'host', 'food'
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
                self.fields['stamp'].queryset = StampDelivery.objects.filter(user=user, status='DISPONIVEL')
        # Filtra os selos se for uma nova criação e o técnico foi passado
        elif user:
            self.fields['stamp'].queryset = StampDelivery.objects.filter(user=user, status='DISPONIVEL')


        

PartFormset = inlineformset_factory(ServiceOrder, Part, fields=['code', 'amount', 'serie', 'description', 'base'], extra=5, can_delete=True)

TimeFormset = inlineformset_factory(ServiceOrder, TimeService, fields='__all__', extra=5, can_delete=True)

